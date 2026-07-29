#!/usr/bin/env python3
"""Verify Phase 3 exit criteria: send prompt to LLM and parse JSON response."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from src.data.repository import RestaurantRepository
from src.input.exceptions import InputValidationError
from src.input.filter_engine import FilterEngine
from src.input.validator import validate_preferences
from src.llm.client import LLMClient
from src.llm.exceptions import LLMEmptyCandidatesError, LLMError
from src.llm.prompt_builder import build_prompt

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filter candidates and request LLM recommendations."
    )
    parser.add_argument("--location", required=True, help="City, e.g. Bangalore")
    parser.add_argument(
        "--budget",
        required=True,
        choices=["low", "medium", "high"],
    )
    parser.add_argument("--cuisine", default=None)
    parser.add_argument("--min-rating", type=float, default=0.0)
    parser.add_argument("--extra", default=None, help="Extra preferences")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--top", type=int, default=5, help="Top N for LLM to rank")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print prompt only; do not call LLM",
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

    filter_result = FilterEngine(repository).filter(preferences)
    if filter_result.is_empty:
        logger.error(filter_result.message or "No candidates found.")
        return 1

    logger.info(
        "Using %d candidates (matched %d)",
        len(filter_result.candidates),
        filter_result.total_matched,
    )

    payload = build_prompt(preferences, filter_result.candidates, top_n=args.top)

    if args.dry_run:
        print("\n--- System Prompt ---")
        print(payload.system_prompt)
        print("\n--- User Prompt ---")
        print(payload.user_prompt)
        return 0

    try:
        client = LLMClient.from_env()
        response = client.recommend(
            preferences,
            filter_result.candidates,
            top_n=args.top,
        )
    except LLMEmptyCandidatesError as exc:
        logger.error(str(exc))
        return 1
    except LLMError as exc:
        logger.error("LLM failed: %s", exc)
        return 1

    print("\nLLM Response (parsed JSON):\n")
    print(json.dumps(response.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
