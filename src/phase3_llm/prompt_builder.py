"""Build LLM prompts from user preferences and candidate restaurants."""

from __future__ import annotations

import json
from typing import Any

from src.phase1_data.models import Restaurant
from src.phase2_input.schemas import UserPreference
from src.phase3_llm.prompt_templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from src.phase3_llm.schemas import PromptPayload

DEFAULT_TOP_N = 5
MAX_NAME_LENGTH = 200
MAX_REST_TYPE_LENGTH = 80


def _serialize_candidate(restaurant: Restaurant) -> dict[str, Any]:
    """Convert a Restaurant to a compact JSON-safe dict for the prompt."""
    cuisines = ", ".join(restaurant.cuisines) if restaurant.cuisines else "N/A"
    return {
        "name": restaurant.name[:MAX_NAME_LENGTH],
        "area": restaurant.area,
        "cuisine": cuisines,
        "rating": restaurant.rating,
        "cost": restaurant.cost_display,
        "rest_type": (restaurant.rest_type or "")[:MAX_REST_TYPE_LENGTH] or None,
    }


def serialize_candidates(candidates: list[Restaurant]) -> str:
    """Serialize candidates to a JSON string for prompt injection."""
    payload = [_serialize_candidate(r) for r in candidates]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_prompt(
    preferences: UserPreference,
    candidates: list[Restaurant],
    *,
    top_n: int = DEFAULT_TOP_N,
) -> PromptPayload:
    """
    Build system and user prompts from preferences and candidates.

    Uses json.dumps for candidate serialization — never manual string concat.
    """
    cuisine = preferences.cuisine or "Any"
    extra = preferences.extra_preferences or "None"

    user_prompt = USER_PROMPT_TEMPLATE.format(
        location=preferences.location,
        budget=preferences.budget.value,
        cuisine=cuisine,
        min_rating=preferences.min_rating,
        extra_preferences=extra,
        candidates_json=serialize_candidates(candidates),
        top_n=min(top_n, len(candidates)),
    )

    return PromptPayload(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
