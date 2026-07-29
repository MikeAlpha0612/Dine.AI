#!/usr/bin/env python3
"""Verify Phase 2 exit criteria: validate preferences and filter candidates."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from src.phase1_data.repository import RestaurantRepository
from src.phase2_input.exceptions import InputValidationError
from src.phase2_input.filter_engine import FilterEngine
from src.phase2_input.validator import validate_preferences

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate user preferences and filter restaurant candidates."
    )
    parser.add_argument("--location", required=True, help="City, e.g. Bangalore")
    parser.add_argument(
        "--budget",
        required=True,
        choices=["low", "medium", "high"],
        help="Budget tier",
    )
    parser.add_argument("--cuisine", default=None, help="Optional cuisine filter")
    parser.add_argument(
        "--min-rating",
        type=float,
        default=0.0,
        help="Minimum rating (0.0-5.0)",
    )
    parser.add_argument(
        "--extra",
        default=None,
        help="Optional free-text preferences (stored for LLM in later phases)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Limit rows loaded from Hugging Face",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of candidates to display",
    )
    args = parser.parse_args()

    try:
        preferences = validate_preferences(
            {
                "location": args.location,
                "budget": args.budget,
                "cuisine": args.cuisine,
                "min_rating": args.min_rating,
                "extra_preferences": args.extra,
            }
        )
    except InputValidationError as exc:
        logger.error("Validation failed: %s", exc)
        return 1

    repository = RestaurantRepository()
    try:
        repository.load(max_rows=args.max_rows)
    except Exception as exc:
        logger.error("Failed to load dataset: %s", exc)
        return 1

    engine = FilterEngine(repository)
    result = engine.filter(preferences)

    print("\nValidated preferences:")
    print(json.dumps(preferences.model_dump(), indent=2))

    if result.message:
        print(f"\n{result.message}")

    if result.is_empty:
        return 1

    print(
        f"\nCandidates: {len(result.candidates)} shown "
        f"({result.total_matched} matched, capped={result.is_capped})\n"
    )

    for index, restaurant in enumerate(result.candidates[: args.top], start=1):
        cuisines = ", ".join(restaurant.cuisines) if restaurant.cuisines else "N/A"
        print(
            f"{index}. {restaurant.name}\n"
            f"   {restaurant.area} | {cuisines}\n"
            f"   Rating: {restaurant.rating} | Cost: {restaurant.cost_display} | "
            f"Budget: {restaurant.budget_tier.value if restaurant.budget_tier else 'unknown'}\n"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
