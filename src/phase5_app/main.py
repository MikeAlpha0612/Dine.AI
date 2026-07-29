"""CLI entry point for the restaurant recommendation app."""

from __future__ import annotations

import argparse
import logging
import sys

from src.phase5_app.service import AppService
from src.phase5_app.ui.forms import validate_form
from src.phase5_app.ui.results import format_recommendation_card, format_result_summary
from src.phase2_input.exceptions import InputValidationError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.phase5_app.main",
        description="AI-powered restaurant recommendation CLI",
    )
    parser.add_argument("--location", required=True, help="City, e.g. Bangalore")
    parser.add_argument(
        "--budget",
        required=True,
        choices=["low", "medium", "high"],
        help="Budget tier",
    )
    parser.add_argument("--cuisine", default=None, help="Optional cuisine filter")
    parser.add_argument("--min-rating", type=float, default=0.0)
    parser.add_argument("--extra", default=None, help="Extra free-text preferences")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Use rule-based ranking only (no LLM API key needed)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    payload, error = validate_form(
        location=args.location,
        budget=args.budget,
        cuisine=args.cuisine,
        min_rating=args.min_rating,
        extra_preferences=args.extra,
    )
    if error:
        logger.error("Validation failed: %s", error)
        return 1

    service = AppService(
        max_rows=args.max_rows,
        use_llm=not args.no_llm,
        top_n=args.top,
    )
    try:
        service.load()
    except Exception as exc:
        logger.error("Failed to load data: %s", exc)
        return 1

    try:
        assert payload is not None
        result = service.recommend(
            location=payload["location"],
            budget=payload["budget"],
            cuisine=payload.get("cuisine"),
            min_rating=payload.get("min_rating", 0.0),
            extra_preferences=payload.get("extra_preferences"),
        )
    except InputValidationError as exc:
        logger.error("%s", exc)
        return 1

    summary = format_result_summary(result)
    if summary:
        print(f"\n{summary}\n")

    if result.is_empty:
        return 1

    for rec in result.recommendations:
        print(format_recommendation_card(rec))
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
