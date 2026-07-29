"""Preference form helpers and validation mapping for UI layers."""

from __future__ import annotations

from typing import Any, Optional

from src.input.exceptions import InputValidationError
from src.input.validator import validate_preferences

BUDGET_OPTIONS = ("low", "medium", "high")


def build_preference_payload(
    *,
    location: str,
    budget: str,
    cuisine: Optional[str] = None,
    min_rating: float = 0.0,
    extra_preferences: Optional[str] = None,
) -> dict[str, Any]:
    """Normalize form fields into a payload for validate_preferences / recommender."""
    return {
        "location": location,
        "budget": budget,
        "cuisine": cuisine or None,
        "min_rating": min_rating,
        "extra_preferences": extra_preferences or None,
    }


def validate_form(
    *,
    location: str,
    budget: str,
    cuisine: Optional[str] = None,
    min_rating: float = 0.0,
    extra_preferences: Optional[str] = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Validate form input.

    Returns (payload, None) on success, or (None, error_message) on failure.
    """
    payload = build_preference_payload(
        location=location,
        budget=budget,
        cuisine=cuisine,
        min_rating=min_rating,
        extra_preferences=extra_preferences,
    )
    try:
        prefs = validate_preferences(payload)
        return prefs.model_dump(), None
    except InputValidationError as exc:
        return None, str(exc)
