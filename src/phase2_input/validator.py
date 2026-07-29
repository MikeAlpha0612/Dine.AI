"""Validate and normalize raw user preference input."""

from __future__ import annotations

import logging
import re
from typing import Any, Mapping

from pydantic import ValidationError

from src.phase1_data.models import Budget
from src.phase2_input.config import EXTRA_PREFERENCES_MAX_LENGTH
from src.phase2_input.exceptions import InputValidationError
from src.phase2_input.schemas import UserPreference

logger = logging.getLogger(__name__)

_MIN_RATING_PATTERN = re.compile(r"^\d+(?:\.\d+)?$")


def _strip_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_budget(value: Any) -> Budget:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise InputValidationError("Budget is required.", field="budget")
    if isinstance(value, Budget):
        return value
    try:
        return Budget(str(value).strip().lower())
    except ValueError as exc:
        raise InputValidationError(
            "Budget must be one of: low, medium, high.",
            field="budget",
        ) from exc


def _parse_min_rating(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        rating = float(value)
    else:
        text = str(value).strip()
        if not _MIN_RATING_PATTERN.match(text):
            raise InputValidationError(
                "Minimum rating must be a number between 0.0 and 5.0.",
                field="min_rating",
            )
        rating = float(text)

    if rating < 0.0 or rating > 5.0:
        raise InputValidationError(
            "Minimum rating must be between 0.0 and 5.0.",
            field="min_rating",
        )
    return rating


def _parse_extra_preferences(value: Any) -> str | None:
    text = _strip_optional(value)
    if text is None:
        return None
    if len(text) > EXTRA_PREFERENCES_MAX_LENGTH:
        logger.warning(
            "extra_preferences truncated from %d to %d characters",
            len(text),
            EXTRA_PREFERENCES_MAX_LENGTH,
        )
        return text[:EXTRA_PREFERENCES_MAX_LENGTH]
    return text


def _normalize_raw(data: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a raw input mapping before schema validation."""
    location = _strip_optional(data.get("location"))
    if not location:
        raise InputValidationError("Location is required.", field="location")

    return {
        "location": location,
        "budget": _parse_budget(data.get("budget")),
        "cuisine": _strip_optional(data.get("cuisine")),
        "min_rating": _parse_min_rating(data.get("min_rating")),
        "extra_preferences": _parse_extra_preferences(data.get("extra_preferences")),
    }


def validate_preferences(data: Mapping[str, Any]) -> UserPreference:
    """
    Validate raw user input and return a UserPreference.

    Accepts a dict-like object with keys: location, budget, cuisine,
    min_rating, extra_preferences.

    Raises:
        InputValidationError: When validation fails with a user-facing message.
    """
    try:
        normalized = _normalize_raw(data)
        return UserPreference.model_validate(normalized)
    except InputValidationError:
        raise
    except ValidationError as exc:
        raise InputValidationError(str(exc.errors()[0]["msg"])) from exc
