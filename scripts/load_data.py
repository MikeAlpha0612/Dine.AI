#!/usr/bin/env python3
"""Verify Phase 1 exit criteria: load data and filter by location."""

from __future__ import annotations

import argparse
import logging
import sys

from src.data.models import FilterCriteria
from src.data.repository import RestaurantRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load Zomato data and run sample filters.")
    parser.add_argument(
        "--location",
        default="Bangalore",
        help="City to filter by (default: Bangalore)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Limit rows loaded from Hugging Face (for quick testing)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of sample results to print",
    )
    args = parser.parse_args()

    repository = RestaurantRepository()
    try:
        repository.load(max_rows=args.max_rows)
    except Exception as exc:
        logger.error("Failed to load dataset: %s", exc)
        return 1

    logger.info("Loaded %d restaurants", repository.count)
    logger.info("Available cities (%d): %s", len(repository.get_locations()), repository.get_locations()[:10])

    criteria = FilterCriteria(location=args.location)
    results = repository.filter_by(criteria)
    logger.info("Found %d restaurants in %s", len(results), args.location)

    if not results:
        logger.warning("No restaurants found for location '%s'", args.location)
        return 1

    print(f"\nTop {args.top} restaurants in {args.location}:\n")
    for index, restaurant in enumerate(results[: args.top], start=1):
        cuisines = ", ".join(restaurant.cuisines) if restaurant.cuisines else "N/A"
        cost = restaurant.cost_display
        print(
            f"{index}. {restaurant.name}\n"
            f"   Area: {restaurant.area} | Cuisine: {cuisines}\n"
            f"   Rating: {restaurant.rating} ({restaurant.votes} votes) | Cost: {cost}\n"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
