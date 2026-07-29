"""Merge LLM rankings with source restaurant data and apply fallbacks."""

from __future__ import annotations

import logging
from difflib import SequenceMatcher

from src.data.models import Restaurant
from src.engine.config import (
    DEFAULT_TOP_N,
    FUZZY_MATCH_THRESHOLD,
    MAX_EXPLANATION_LENGTH,
)
from src.engine.schemas import Recommendation
from src.input.schemas import UserPreference
from src.llm.schemas import LLMRecommendationItem, LLMResponse

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    return " ".join(name.lower().split())


def _cuisine_label(restaurant: Restaurant) -> str:
    return ", ".join(restaurant.cuisines) if restaurant.cuisines else "N/A"


def _cost_label(restaurant: Restaurant) -> str:
    if restaurant.cost_display and restaurant.cost_display != "unknown":
        return restaurant.cost_display
    return "Cost not available"


def default_explanation(restaurant: Restaurant, preferences: UserPreference) -> str:
    """Template explanation used for fallback / missing LLM explanations."""
    cuisine = _cuisine_label(restaurant)
    return (
        f"Highly rated {cuisine} option in {preferences.location} "
        f"within your {preferences.budget.value} budget."
    )


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_name(a), _normalize_name(b)).ratio()


def match_restaurant(
    name: str,
    candidates: list[Restaurant],
    *,
    threshold: float = FUZZY_MATCH_THRESHOLD,
) -> Restaurant | None:
    """
    Match an LLM restaurant name against candidates.

    Prefers exact (case-insensitive) match, then best fuzzy match above threshold.
    """
    needle = _normalize_name(name)
    for restaurant in candidates:
        if _normalize_name(restaurant.name) == needle:
            return restaurant

    best: Restaurant | None = None
    best_score = 0.0
    for restaurant in candidates:
        score = _similarity(name, restaurant.name)
        if score > best_score:
            best_score = score
            best = restaurant

    if best is not None and best_score >= threshold:
        logger.info(
            "Fuzzy-matched '%s' -> '%s' (score=%.2f)",
            name,
            best.name,
            best_score,
        )
        return best

    return None


def enrich_recommendation(
    restaurant: Restaurant,
    *,
    rank: int,
    explanation: str | None,
    preferences: UserPreference,
) -> Recommendation:
    """Build a Recommendation from a dataset restaurant and optional LLM text."""
    text = (explanation or "").strip() or default_explanation(restaurant, preferences)
    if len(text) > MAX_EXPLANATION_LENGTH:
        text = text[: MAX_EXPLANATION_LENGTH - 3] + "..."

    return Recommendation(
        rank=rank,
        name=restaurant.name,
        cuisine=_cuisine_label(restaurant),
        rating=restaurant.rating,
        estimated_cost=_cost_label(restaurant),
        explanation=text,
        restaurant_id=restaurant.id,
        area=restaurant.area,
    )


def fallback_recommendations(
    candidates: list[Restaurant],
    preferences: UserPreference,
    *,
    top_n: int = DEFAULT_TOP_N,
) -> list[Recommendation]:
    """Rule-based top-N by rating when the LLM is unavailable or incomplete."""
    selected = candidates[:top_n]
    return [
        enrich_recommendation(
            restaurant,
            rank=index,
            explanation=None,
            preferences=preferences,
        )
        for index, restaurant in enumerate(selected, start=1)
    ]


def merge_llm_with_candidates(
    llm_response: LLMResponse,
    candidates: list[Restaurant],
    preferences: UserPreference,
    *,
    top_n: int = DEFAULT_TOP_N,
) -> list[Recommendation]:
    """
    Cross-reference LLM picks against candidates, enrich, and backfill to top_n.

    - Drops hallucinated names (EC-R01)
    - Fuzzy-matches minor misspellings (EC-R02)
    - Deduplicates (EC-R05)
    - Backfills from remaining candidates by rating (EC-R03, EC-R12)
    - Caps at top_n (EC-R04)
    """
    used_ids: set[str] = set()
    results: list[Recommendation] = []

    sorted_items = sorted(llm_response.recommendations, key=lambda item: item.rank)

    for item in sorted_items:
        if len(results) >= top_n:
            break

        matched = match_restaurant(item.name, candidates)
        if matched is None:
            logger.warning("Dropping hallucinated restaurant: '%s'", item.name)
            continue

        if matched.id in used_ids:
            logger.debug("Skipping duplicate recommendation: '%s'", matched.name)
            continue

        used_ids.add(matched.id)
        results.append(
            enrich_recommendation(
                matched,
                rank=len(results) + 1,
                explanation=item.explanation,
                preferences=preferences,
            )
        )

    if len(results) < top_n:
        for restaurant in candidates:
            if len(results) >= top_n:
                break
            if restaurant.id in used_ids:
                continue
            used_ids.add(restaurant.id)
            results.append(
                enrich_recommendation(
                    restaurant,
                    rank=len(results) + 1,
                    explanation=None,
                    preferences=preferences,
                )
            )

    return results
