"""Load multi-city Zomato data (includes Delhi, Mumbai, and other metros)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import pandas as pd

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
    METRO_DATASET_CACHE,
    METRO_DATASET_URL,
)

logger = logging.getLogger(__name__)

# City labels that are Bangalore neighborhoods mis-tagged in the metro CSV
_BANGALORE_AREAS = {
    "banaswadi",
    "ulsoor",
    "magrath road",
    "malleshwaram",
}


def _normalize_city(value: str) -> str:
    city = str(value).strip()
    if city.lower() in _BANGALORE_AREAS:
        return "Bangalore"
    return city


def _to_hf_schema(group: pd.DataFrame, city: str, place: str, name: str) -> dict[str, Any]:
    """Aggregate menu-item rows into one HF-compatible restaurant record."""
    cuisine_col = "Cuisine " if "Cuisine " in group.columns else "Cuisine"
    cuisines = sorted(
        {
            str(c).strip()
            for c in group[cuisine_col].dropna().unique()
            if str(c).strip()
        }
    )

    dining = pd.to_numeric(group.get("Dining_Rating"), errors="coerce")
    delivery = pd.to_numeric(group.get("Delivery_Rating"), errors="coerce")
    rating = dining.dropna()
    if rating.empty:
        rating = delivery.dropna()
    rate_value = float(rating.median()) if not rating.empty else None

    dining_votes = pd.to_numeric(group.get("Dining_Votes"), errors="coerce").fillna(0)
    delivery_votes = pd.to_numeric(group.get("Delivery_Votes"), errors="coerce").fillna(0)
    votes = int((dining_votes + delivery_votes).max())

    prices = pd.to_numeric(group.get("Prices"), errors="coerce").dropna()
    # Estimate cost-for-two from typical item prices
    if not prices.empty:
        cost = int(max(100, min(5000, round(float(prices.median()) * 2))))
        cost_str = str(cost)
    else:
        cost_str = None

    rate_str = f"{rate_value:.1f}/5" if rate_value is not None else "-"

    return {
        COL_NAME: name,
        COL_ADDRESS: f"{place}, {city}",
        COL_LOCATION: place,
        COL_CUISINES: ", ".join(cuisines) if cuisines else None,
        COL_COST: cost_str,
        COL_RATE: rate_str,
        COL_VOTES: votes,
        COL_REST_TYPE: None,
        COL_LISTED_CITY: city,
    }


def load_metro_rows(*, max_restaurants: Optional[int] = None) -> list[dict[str, Any]]:
    """
    Load and aggregate the multi-city Zomato CSV into HF-compatible rows.

    Source covers New Delhi, Mumbai, Bangalore, Hyderabad, Chennai, and more.
    """
    cache_path = Path(METRO_DATASET_CACHE)
    try:
        if cache_path.exists():
            logger.info("Loading metro dataset from cache: %s", cache_path)
            df = pd.read_csv(cache_path)
        else:
            logger.info("Downloading metro dataset from %s", METRO_DATASET_URL)
            df = pd.read_csv(METRO_DATASET_URL)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache_path, index=False)
            logger.info("Cached metro dataset to %s", cache_path)
    except Exception as exc:
        logger.warning("Failed to load metro dataset: %s", exc)
        return []

    if df.empty:
        return []

    df = df.copy()
    df["City"] = df["City"].map(_normalize_city)
    df["Place_Name"] = df["Place_Name"].astype(str).str.strip()
    df["Restaurant_Name"] = df["Restaurant_Name"].astype(str).str.strip()
    df = df[df["Restaurant_Name"].notna() & (df["Restaurant_Name"] != "")]
    df = df[df["City"].notna() & (df["City"] != "")]

    grouped = df.groupby(["City", "Place_Name", "Restaurant_Name"], dropna=False)
    rows: list[dict[str, Any]] = []
    for (city, place, name), group in grouped:
        rows.append(_to_hf_schema(group, str(city), str(place), str(name)))
        if max_restaurants is not None and len(rows) >= max_restaurants:
            break

    logger.info("Loaded %d multi-city restaurants (Delhi/Mumbai included)", len(rows))
    return rows
