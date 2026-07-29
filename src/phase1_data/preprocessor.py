"""Clean and normalize raw Zomato dataset rows."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Optional

from src.phase1_data.config import (
    BUDGET_LOW_MAX,
    BUDGET_MEDIUM_MAX,
    COL_ADDRESS,
    COL_COST,
    COL_CUISINES,
    COL_LISTED_CITY,
    COL_LOCATION,
    COL_NAME,
    COL_RATE,
    COL_REST_TYPE,
    COL_VOTES,
    LOCATION_ALIASES,
    MAX_RATING,
    MIN_RATING,
)
from src.phase1_data.models import Budget, Restaurant

logger = logging.getLogger(__name__)

# rate field: "4.1/5", "-", "NEW", etc.
_RATE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")

# cost: "800", "300-500", "₹1,000 - ₹1,500"
_COST_RANGE_PATTERN = re.compile(
    r"(\d[\d,]*)\s*(?:-\s*(\d[\d,]*))?",
)

# Known Indian cities for address parsing (longest match first)
_KNOWN_CITIES = sorted(
    set(LOCATION_ALIASES.values())
    | {
        "Bangalore",
        "Mumbai",
        "New Delhi",
        "Delhi",
        "Gurgaon",
        "Hyderabad",
        "Chennai",
        "Kolkata",
        "Pune",
        "Ahmedabad",
        "Jaipur",
        "Lucknow",
        "Chandigarh",
        "Indore",
        "Coimbatore",
        "Kochi",
        "Goa",
        "Raipur",
        "Noida",
        "Faridabad",
        "Ghaziabad",
    },
    key=len,
    reverse=True,
)


def normalize_location_name(value: str) -> str:
    """Normalize a city/location string to a canonical form."""
    cleaned = value.strip()
    if not cleaned:
        return cleaned
    alias = LOCATION_ALIASES.get(cleaned.lower())
    if alias:
        return alias
    return cleaned.title()


def parse_rating(raw: Any) -> float:
    """Parse rating from strings like '4.1/5', '-', or 'NEW'."""
    if raw is None:
        return MIN_RATING
    text = str(raw).strip()
    if not text or text in {"-", "NEW", "nan", "None"}:
        return MIN_RATING
    match = _RATE_PATTERN.search(text)
    if not match:
        return MIN_RATING
    rating = float(match.group(1))
    return max(MIN_RATING, min(MAX_RATING, rating))


def parse_cost(raw: Any) -> tuple[Optional[int], str]:
    """
    Parse cost-for-two into numeric value and display string.

    Returns (cost_for_two, cost_display). cost_for_two is None when unknown.
    """
    if raw is None:
        return None, "unknown"
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "none", "-"}:
        return None, "unknown"

    match = _COST_RANGE_PATTERN.search(text.replace("₹", ""))
    if not match:
        return None, text or "unknown"

    low = int(match.group(1).replace(",", ""))
    high_str = match.group(2)
    if high_str:
        high = int(high_str.replace(",", ""))
        midpoint = (low + high) // 2
        return midpoint, f"{low}-{high}"

    return low, str(low)


def cost_to_budget_tier(cost: Optional[int]) -> Optional[Budget]:
    """Map numeric cost-for-two to a budget tier."""
    if cost is None:
        return None
    if cost <= BUDGET_LOW_MAX:
        return Budget.LOW
    if cost <= BUDGET_MEDIUM_MAX:
        return Budget.MEDIUM
    return Budget.HIGH


def parse_cuisines(raw: Any) -> list[str]:
    """Split comma-separated cuisines into a normalized list."""
    if raw is None:
        return []
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return []
    parts = re.split(r"[,;/]", text)
    return [part.strip() for part in parts if part.strip()]


def _is_known_city(value: str) -> bool:
    cleaned = value.strip()
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if lowered in LOCATION_ALIASES:
        return True
    return any(city.lower() == lowered for city in _KNOWN_CITIES)


def extract_city_from_address(address: str) -> Optional[str]:
    """Extract city name from a Zomato address string."""
    if not address or not address.strip():
        return None

    # Try matching known cities anywhere in the address
    address_lower = address.lower()
    for city in _KNOWN_CITIES:
        if city.lower() in address_lower:
            return normalize_location_name(city)

    # Fallback: last comma-separated segment only if it is a known city
    segments = [segment.strip() for segment in address.split(",") if segment.strip()]
    if segments:
        candidate = normalize_location_name(segments[-1])
        if _is_known_city(candidate):
            return candidate
    return None


def _make_restaurant_id(name: str, area: str, address: str) -> str:
    key = f"{name}|{area}|{address}".lower()
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def preprocess_row(row: dict[str, Any], row_index: int = 0) -> Optional[Restaurant]:
    """
    Convert a raw dataset row into a Restaurant, or None if critical fields are missing.
    """
    name = str(row.get(COL_NAME, "") or "").strip()
    area = str(row.get(COL_LOCATION, "") or "").strip()
    address = str(row.get(COL_ADDRESS, "") or "").strip()
    listed = str(row.get(COL_LISTED_CITY, "") or "").strip()
    listed_city = normalize_location_name(listed) if listed else ""

    if not name:
        logger.warning("Skipping row %d: missing name", row_index)
        return None

    # Prefer explicit city column when present (nationwide datasets)
    if listed_city:
        city = listed_city
    else:
        city = extract_city_from_address(address)

    if not city and not area:
        logger.warning("Skipping row %d: missing location for '%s'", row_index, name)
        return None

    location = city or normalize_location_name(area)
    if not location:
        logger.warning("Skipping row %d: missing city for '%s'", row_index, name)
        return None

    cost, cost_display = parse_cost(row.get(COL_COST))
    cuisines = parse_cuisines(row.get(COL_CUISINES))

    rest_type_raw = row.get(COL_REST_TYPE)
    rest_type = str(rest_type_raw).strip() if rest_type_raw not in (None, "nan") else None
    if rest_type == "":
        rest_type = None

    votes_raw = row.get(COL_VOTES, 0)
    try:
        votes = int(votes_raw) if votes_raw is not None else 0
    except (TypeError, ValueError):
        votes = 0

    return Restaurant(
        id=_make_restaurant_id(name, area, address),
        name=name,
        location=location,
        area=area or location,
        cuisines=cuisines,
        cost_for_two=cost,
        cost_display=cost_display,
        budget_tier=cost_to_budget_tier(cost),
        rating=parse_rating(row.get(COL_RATE)),
        votes=max(0, votes),
        rest_type=rest_type,
        address=address or None,
    )


def preprocess_rows(rows: list[dict[str, Any]]) -> list[Restaurant]:
    """Preprocess all rows, deduplicating by (name, location, area)."""
    seen: dict[tuple[str, str, str], Restaurant] = {}

    for index, row in enumerate(rows):
        restaurant = preprocess_row(row, row_index=index)
        if restaurant is None:
            continue

        key = (restaurant.name.lower(), restaurant.location.lower(), restaurant.area.lower())
        existing = seen.get(key)
        if existing is None or restaurant.rating > existing.rating:
            seen[key] = restaurant

    return list(seen.values())
