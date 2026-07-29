"""Rule-based candidate filtering for restaurant recommendations."""

from __future__ import annotations

import logging

from src.phase1_data.models import FilterCriteria
from src.phase1_data.preprocessor import extract_city_from_address, normalize_location_name
from src.phase1_data.repository import RestaurantRepository
from src.phase2_input.config import MAX_CANDIDATES
from src.phase2_input.schemas import FilterResult, UserPreference

logger = logging.getLogger(__name__)

_MAX_LOCATION_SUGGESTIONS = 8


class FilterEngine:
    """Filter restaurants from the repository based on user preferences."""

    def __init__(
        self,
        repository: RestaurantRepository,
        *,
        max_candidates: int = MAX_CANDIDATES,
    ) -> None:
        self._repository = repository
        self._max_candidates = max_candidates

    def filter(self, preferences: UserPreference) -> FilterResult:
        """
        Return a bounded, ranked candidate list for the given preferences.

        Does not call the LLM. Applies location, rating, cuisine, and budget
        filters, then caps results to max_candidates.
        """
        available_locations = self._repository.get_locations()
        resolved_location = self._resolve_location(preferences.location, available_locations)

        if resolved_location is None:
            message = self._unknown_location_message(
                preferences.location,
                available_locations,
            )
            return FilterResult(
                candidates=[],
                total_matched=0,
                is_capped=False,
                message=message,
                preferences=preferences,
            )

        criteria = FilterCriteria(
            location=resolved_location,
            cuisine=preferences.cuisine,
            min_rating=preferences.min_rating,
            budget=preferences.budget,
        )
        matched = self._repository.filter_by(criteria)
        total_matched = len(matched)

        if total_matched == 0:
            return FilterResult(
                candidates=[],
                total_matched=0,
                is_capped=False,
                message=self._empty_filter_message(preferences),
                preferences=preferences,
            )

        is_capped = total_matched > self._max_candidates
        candidates = matched[: self._max_candidates]

        message = None
        if is_capped:
            message = (
                f"Showing top {self._max_candidates} of {total_matched} matching "
                f"restaurants in {resolved_location}."
            )

        logger.info(
            "Filter returned %d candidates (%d matched, capped=%s)",
            len(candidates),
            total_matched,
            is_capped,
        )

        return FilterResult(
            candidates=candidates,
            total_matched=total_matched,
            is_capped=is_capped,
            message=message,
            preferences=preferences,
        )

    @staticmethod
    def _location_exists(location: str, available: list[str]) -> bool:
        target = location.lower()
        return any(loc.lower() == target for loc in available)

    @staticmethod
    def _resolve_location(requested: str, available: list[str]) -> str | None:
        """Resolve a user location to a known city in the dataset."""
        normalized = normalize_location_name(requested.strip())
        if FilterEngine._location_exists(normalized, available):
            return normalized

        extracted = extract_city_from_address(requested)
        if extracted and FilterEngine._location_exists(extracted, available):
            return extracted

        # Case-insensitive / substring match against available cities
        needle = normalized.lower()
        exact = [c for c in available if c.lower() == needle]
        if exact:
            return exact[0]

        contains = [c for c in available if needle in c.lower() or c.lower() in needle]
        if len(contains) == 1:
            return contains[0]

        return None

    @staticmethod
    def _unknown_location_message(requested: str, available: list[str]) -> str:
        preferred = [
            "Bangalore",
            "New Delhi",
            "Mumbai",
            "Hyderabad",
            "Chennai",
            "Pune",
            "Kolkata",
            "Jaipur",
        ]
        top = [c for c in preferred if c in available]
        rest = [c for c in available if c not in top]
        preview = (top + rest)[:_MAX_LOCATION_SUGGESTIONS]
        suggestions = ", ".join(preview)
        suffix = f" (and {len(available) - len(preview)} more)" if len(available) > len(preview) else ""
        return (
            f"No restaurants found for '{requested}'. "
            f"Try one of: {suggestions}{suffix}"
        )

    @staticmethod
    def _empty_filter_message(preferences: UserPreference) -> str:
        filters = [
            f"location={preferences.location}",
            f"budget={preferences.budget.value}",
        ]
        if preferences.cuisine:
            filters.append(f"cuisine={preferences.cuisine}")
        if preferences.min_rating > 0:
            filters.append(f"min_rating={preferences.min_rating}")

        active = ", ".join(filters)
        suggestions = []
        if preferences.cuisine:
            suggestions.append("removing the cuisine filter")
        if preferences.min_rating > 0:
            suggestions.append("lowering the minimum rating")
        suggestions.append("choosing a different budget tier")

        hint = "; ".join(suggestions)
        return (
            f"No restaurants match your preferences in {preferences.location} "
            f"({active}). Try {hint}."
        )
