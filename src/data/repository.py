"""In-memory restaurant data access."""

from __future__ import annotations

import logging
from typing import Optional

from src.data.exceptions import RepositoryNotReadyError
from src.data.loader import load_raw_rows
from src.data.models import Budget, FilterCriteria, Restaurant
from src.data.preprocessor import normalize_location_name, preprocess_rows

logger = logging.getLogger(__name__)


class RestaurantRepository:
    """Load, store, and query preprocessed restaurant records."""

    def __init__(self) -> None:
        self._restaurants: list[Restaurant] = []
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def count(self) -> int:
        return len(self._restaurants)

    def load(
        self,
        *,
        max_rows: Optional[int] = None,
        use_cache: bool = True,
    ) -> None:
        """Load data from Hugging Face, preprocess, and mark repository ready."""
        raw_rows = load_raw_rows(max_rows=max_rows, use_cache=use_cache)
        self._restaurants = preprocess_rows(raw_rows)
        self._ready = True
        logger.info("Repository ready with %d restaurants", len(self._restaurants))

        if not self._restaurants:
            logger.warning("Repository loaded but contains zero valid restaurants")

    def load_from_rows(self, rows: list[dict]) -> None:
        """Load from pre-built raw rows (used in tests)."""
        self._restaurants = preprocess_rows(rows)
        self._ready = True

    def load_from_restaurants(self, restaurants: list[Restaurant]) -> None:
        """Load from pre-built Restaurant objects (used in tests)."""
        self._restaurants = list(restaurants)
        self._ready = True

    def _ensure_ready(self) -> None:
        if not self._ready:
            raise RepositoryNotReadyError(
                "Restaurant data is not loaded yet. Call load() before querying."
            )

    def get_all(self) -> list[Restaurant]:
        """Return all restaurants."""
        self._ensure_ready()
        return list(self._restaurants)

    def get_locations(self) -> list[str]:
        """Return sorted unique city locations."""
        self._ensure_ready()
        return sorted({r.location for r in self._restaurants})

    def get_cuisines(self) -> list[str]:
        """Return sorted unique cuisines."""
        self._ensure_ready()
        cuisines: set[str] = set()
        for restaurant in self._restaurants:
            cuisines.update(restaurant.cuisines)
        return sorted(cuisines)

    def filter_by(self, criteria: FilterCriteria) -> list[Restaurant]:
        """
        Filter restaurants by location, cuisine, minimum rating, and budget.

        Results are sorted by rating (desc), then votes (desc), then name (asc).
        """
        self._ensure_ready()
        results = self._restaurants

        if criteria.location:
            target = normalize_location_name(criteria.location)
            results = [
                r
                for r in results
                if r.location.lower() == target.lower()
                or target.lower() in (r.address or "").lower()
            ]

        if criteria.min_rating > 0:
            results = [r for r in results if r.rating >= criteria.min_rating]

        if criteria.cuisine:
            needle = criteria.cuisine.strip().lower()
            results = [
                r
                for r in results
                if any(needle in cuisine.lower() for cuisine in r.cuisines)
            ]

        if criteria.budget is not None:
            results = [r for r in results if r.budget_tier == criteria.budget]

        results.sort(key=lambda r: (-r.rating, -r.votes, r.name.lower()))
        return results
