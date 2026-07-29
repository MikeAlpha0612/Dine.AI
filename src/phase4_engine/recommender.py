"""End-to-end recommendation orchestrator."""

from __future__ import annotations

import logging
from typing import Mapping, Optional, Union

from src.phase1_data.models import Restaurant
from src.phase1_data.repository import RestaurantRepository
from src.phase4_engine.config import DEFAULT_TOP_N
from src.phase4_engine.ranker import fallback_recommendations, merge_llm_with_candidates
from src.phase4_engine.schemas import RecommendationResult
from src.phase2_input.exceptions import InputValidationError
from src.phase2_input.filter_engine import FilterEngine
from src.phase2_input.schemas import UserPreference
from src.phase2_input.validator import validate_preferences
from src.phase3_llm.client import LLMClient
from src.phase3_llm.exceptions import LLMError

logger = logging.getLogger(__name__)

PreferenceInput = Union[UserPreference, Mapping[str, object]]


class Recommender:
    """
    Orchestrates: validate → filter → LLM → parse → enrich → RecommendationResult.

    Falls back to rule-based top-N when the LLM fails.
    """

    def __init__(
        self,
        repository: RestaurantRepository,
        llm_client: Optional[LLMClient] = None,
        *,
        top_n: int = DEFAULT_TOP_N,
        filter_engine: Optional[FilterEngine] = None,
    ) -> None:
        self._repository = repository
        self._llm = llm_client
        self._top_n = top_n
        self._filter = filter_engine or FilterEngine(repository)

    @classmethod
    def from_env(cls, repository: RestaurantRepository, **kwargs) -> Recommender:
        return cls(repository, llm_client=LLMClient.from_env(), **kwargs)

    def recommend(self, preferences: PreferenceInput) -> RecommendationResult:
        """
        Produce validated recommendations for the given preferences.

        Accepts a UserPreference or a raw dict (validated via validate_preferences).
        """
        prefs = self._coerce_preferences(preferences)
        filter_result = self._filter.filter(prefs)

        if filter_result.is_empty:
            return RecommendationResult(
                recommendations=[],
                summary=None,
                preferences=prefs,
                used_fallback=False,
                message=filter_result.message,
            )

        candidates = list(filter_result.candidates)

        if self._llm is None:
            logger.info("No LLM client configured; using fallback recommender")
            return self._fallback_result(
                candidates,
                prefs,
                message="AI ranking unavailable. Showing top-rated matches.",
            )

        try:
            llm_response = self._llm.recommend(
                prefs,
                candidates,
                top_n=self._top_n,
            )
            recommendations = merge_llm_with_candidates(
                llm_response,
                candidates,
                prefs,
                top_n=self._top_n,
            )
            if not recommendations:
                logger.warning("LLM produced no valid matches; using fallback")
                return self._fallback_result(
                    candidates,
                    prefs,
                    message=(
                        "AI recommendations could not be matched. "
                        "Showing top-rated matches."
                    ),
                )

            return RecommendationResult(
                recommendations=recommendations,
                summary=llm_response.summary,
                preferences=prefs,
                used_fallback=False,
                message=filter_result.message,
            )

        except LLMError as exc:
            logger.warning("LLM pipeline failed (%s); using fallback", exc)
            return self._fallback_result(
                candidates,
                prefs,
                message=f"AI summary unavailable ({exc}). Showing top-rated matches.",
            )

    def _fallback_result(
        self,
        candidates: list[Restaurant],
        preferences: UserPreference,
        *,
        message: str,
    ) -> RecommendationResult:
        recommendations = fallback_recommendations(
            candidates,
            preferences,
            top_n=self._top_n,
        )
        summary = (
            f"Top {len(recommendations)} restaurants in {preferences.location} "
            f"for a {preferences.budget.value} budget."
            if recommendations
            else None
        )
        return RecommendationResult(
            recommendations=recommendations,
            summary=summary,
            preferences=preferences,
            used_fallback=True,
            message=message,
        )

    @staticmethod
    def _coerce_preferences(preferences: PreferenceInput) -> UserPreference:
        if isinstance(preferences, UserPreference):
            return preferences
        return validate_preferences(preferences)
