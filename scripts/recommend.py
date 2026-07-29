#!/usr/bin/env python3
"""Verify Phase 4 exit criteria: recommender.recommend(preferences) -> RecommendationResult."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from src.data.repository import RestaurantRepository
from src.engine.recommender import Recommender
from src.input.exceptions import InputValidationError
from src.llm.client import LLMClient
from src.llm.config import LLMConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the recommendation engine.")
    parser.add_argument("--location", required=True)
    parser.add_argument("--budget", required=True, choices=["low", "medium", "high"])
    parser.add_argument("--cuisine", default=None)
    parser.add_argument("--min-rating", type=float, default=0.0)
    parser.add_argument("--extra", default=None)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM and use rule-based fallback ranking",
    )
    args = parser.parse_args()

    repository = RestaurantRepository()
    try:
        repository.load(max_rows=args.max_rows)
    except Exception as exc:
        logger.error("Failed to load dataset: %s", exc)
        return 1

    llm_client = None
    if not args.no_llm:
        try:
            llm_client = LLMClient(LLMConfig.from_env())
        except ValueError as exc:
            logger.warning("%s — using fallback ranking.", exc)
            llm_client = None

    recommender = Recommender(repository, llm_client, top_n=args.top)

    try:
        result = recommender.recommend(
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

    if result.message:
        print(f"\n{result.message}")

    if result.is_empty:
        return 1

    print(f"\nUsed fallback: {result.used_fallback}")
    if result.summary:
        print(f"Summary: {result.summary}\n")

    for rec in result.recommendations:
        print(
            f"#{rec.rank}  {rec.name}\n"
            f"   {rec.cuisine} · ★ {rec.rating} · ₹{rec.estimated_cost}\n"
            f"   {rec.explanation}\n"
        )

    print("\nJSON:")
    print(
        json.dumps(
            result.model_dump(exclude={"preferences"}),
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
