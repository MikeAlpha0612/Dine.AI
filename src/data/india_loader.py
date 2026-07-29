"""Load India-wide Swiggy restaurant data (many cities nationwide)."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from datasets import load_dataset

from src.data.config import (
    COL_ADDRESS,
    COL_COST,
    COL_CUISINES,
    COL_LISTED_CITY,
    COL_LOCATION,
    COL_NAME,
    COL_RATE,
    COL_REST_TYPE,
    COL_VOTES,
    INDIA_DATASET_NAME,
    INDIA_DATASET_SPLIT,
)
from src.data.preprocessor import normalize_location_name

logger = logging.getLogger(__name__)

_VOTES_PATTERN = re.compile(r"(\d+)")


def _parse_city_field(raw: Any) -> tuple[str, str]:
    """
    Parse Swiggy city field into (area, city).

    Examples:
      "BTM,Bangalore" -> ("BTM", "Bangalore")
      "Indirapuram,Delhi" -> ("Indirapuram", "New Delhi")
      "Noida-1" -> ("Noida-1", "Noida")
      "Bikaner" -> ("Bikaner", "Bikaner")
    """
    text = str(raw or "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return "", ""

    if "," in text:
        area, city = text.rsplit(",", 1)
        return area.strip(), normalize_location_name(city.strip())

    # Strip trailing -1 / -2 sector suffixes used by Swiggy
    base = re.sub(r"-\d+$", "", text).strip() or text
    return text, normalize_location_name(base)


def _parse_votes(raw: Any) -> int:
    if raw is None:
        return 0
    if isinstance(raw, (int, float)):
        return int(raw)
    match = _VOTES_PATTERN.search(str(raw).replace(",", ""))
    return int(match.group(1)) if match else 0


def _parse_cost(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "none", "null", "--", "na"}:
        return None
    # Keep digits so preprocessor can parse "₹ 300" / "300 for two"
    return text


def _parse_rating(raw: Any) -> str:
    if raw is None:
        return "-"
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "none", "null", "--", "na", "new"}:
        return "-"
    try:
        value = float(text)
        return f"{value:.1f}/5"
    except ValueError:
        return text if "/" in text else f"{text}/5"


def _row_to_hf_schema(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    name = str(row.get("name") or "").strip()
    if not name:
        return None

    area, city = _parse_city_field(row.get("city"))
    if not city:
        return None

    address = str(row.get("address") or "").strip()
    if not address:
        address = f"{area}, {city}" if area else city

    cuisine = row.get("cuisine")
    cuisine_text = str(cuisine).strip() if cuisine not in (None, "") else None

    return {
        COL_NAME: name,
        COL_ADDRESS: address,
        COL_LOCATION: area or city,
        COL_CUISINES: cuisine_text,
        COL_COST: _parse_cost(row.get("cost")),
        COL_RATE: _parse_rating(row.get("rating")),
        COL_VOTES: _parse_votes(row.get("rating_count")),
        COL_REST_TYPE: None,
        COL_LISTED_CITY: city,
    }


def load_india_rows(*, max_rows: Optional[int] = None) -> list[dict[str, Any]]:
    """
    Load India-wide restaurants from Hugging Face (Swiggy listings).

    Covers 800+ city/locality labels across India after city parsing.
    """
    try:
        logger.info("Loading India-wide dataset %s", INDIA_DATASET_NAME)
        dataset = load_dataset(INDIA_DATASET_NAME, split=INDIA_DATASET_SPLIT)
    except Exception as exc:
        logger.warning("Failed to load India-wide dataset: %s", exc)
        return []

    if len(dataset) == 0:
        return []

    # When capping, keep a fair multi-city sample (major cities first)
    if max_rows is not None and max_rows < len(dataset):
        from collections import defaultdict
        import random

        by_city: dict[str, list[int]] = defaultdict(list)
        for index, city_raw in enumerate(dataset["city"]):
            _, city = _parse_city_field(city_raw)
            if city:
                by_city[city].append(index)

        major = [
            "Bangalore",
            "New Delhi",
            "Mumbai",
            "Hyderabad",
            "Chennai",
            "Pune",
            "Kolkata",
            "Jaipur",
            "Ahmedabad",
            "Lucknow",
            "Surat",
            "Kanpur",
            "Nagpur",
            "Indore",
            "Bhopal",
            "Patna",
            "Chandigarh",
            "Goa",
            "Kochi",
            "Coimbatore",
            "Mysore",
            "Varanasi",
            "Amritsar",
            "Guwahati",
            "Ranchi",
            "Dehradun",
        ]
        selected: list[int] = []
        remaining_cities = [c for c in by_city if c not in major]
        random.Random(42).shuffle(remaining_cities)

        # Reserve slots for major cities so demos still cover them
        major_quota = max(20, max_rows // 40)
        for city in major:
            if city in by_city:
                selected.extend(by_city[city][:major_quota])

        leftover = max(0, max_rows - len(selected))
        per_city = max(1, leftover // max(1, len(remaining_cities))) if leftover else 0
        for city in remaining_cities:
            if len(selected) >= max_rows:
                break
            selected.extend(by_city[city][:per_city])

        selected = selected[:max_rows]
        dataset = dataset.select(selected)

    rows: list[dict[str, Any]] = []
    for row in dataset:
        converted = _row_to_hf_schema(dict(row))
        if converted is not None:
            rows.append(converted)

    cities = {r[COL_LISTED_CITY] for r in rows}
    logger.info(
        "Loaded %d India-wide restaurants across %d cities",
        len(rows),
        len(cities),
    )
    return rows
