"""Shared application service for CLI, web, and API."""

from __future__ import annotations

import logging
from typing import Optional

from src.phase1_data.repository import RestaurantRepository
from src.phase4_engine.recommender import Recommender
from src.phase4_engine.schemas import RecommendationResult
from src.phase2_input.exceptions import InputValidationError
from src.phase3_llm.client import LLMClient
from src.phase3_llm.config import LLMConfig

logger = logging.getLogger(__name__)


class AppService:
    """Loads data once and exposes recommendation requests."""

    def __init__(
        self,
        *,
        max_rows: Optional[int] = None,
        use_llm: bool = True,
        top_n: int = 5,
    ) -> None:
        self._max_rows = max_rows
        self._use_llm = use_llm
        self._top_n = top_n
        self._repository = RestaurantRepository()
        self._recommender: Optional[Recommender] = None
        self._ready = False
        self._load_error: Optional[str] = None

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    @property
    def restaurant_count(self) -> int:
        return self._repository.count if self._ready else 0

    def load(self) -> None:
        """Load dataset and initialize recommender."""
        try:
            self._repository.load(max_rows=self._max_rows)
            llm_client = None
            if self._use_llm:
                try:
                    llm_client = LLMClient(LLMConfig.from_env())
                except ValueError as exc:
                    logger.warning("%s — continuing without LLM.", exc)
                    llm_client = None

            self._recommender = Recommender(
                self._repository,
                llm_client,
                top_n=self._top_n,
            )
            self._ready = True
            self._load_error = None
            logger.info("App service ready (%d restaurants)", self._repository.count)
        except Exception as exc:
            self._ready = False
            self._load_error = str(exc)
            logger.error("Failed to load app service: %s", exc)
            raise

    def recommend(
        self,
        *,
        location: str,
        budget: str,
        cuisine: Optional[str] = None,
        min_rating: float = 0.0,
        extra_preferences: Optional[str] = None,
    ) -> RecommendationResult:
        if not self._ready or self._recommender is None:
            raise RuntimeError(
                self._load_error or "Application is still loading restaurant data."
            )

        return self._recommender.recommend(
            {
                "location": location,
                "budget": budget,
                "cuisine": cuisine,
                "min_rating": min_rating,
                "extra_preferences": extra_preferences,
            }
        )

    def get_locations(self) -> list[str]:
        if not self._ready:
            return []
        return self._repository.get_locations()

    def get_cuisines(self, location: Optional[str] = None) -> list[str]:
        if not self._ready:
            return []
        restaurants = self._repository.get_all()
        if location:
            from src.phase1_data.preprocessor import normalize_location_name

            target = normalize_location_name(location).lower()
            restaurants = [r for r in restaurants if r.location.lower() == target]
        cuisines: set[str] = set()
        for restaurant in restaurants:
            cuisines.update(restaurant.cuisines)
        return sorted(cuisines)

    def search_restaurants(
        self,
        *,
        location: str,
        cuisine: Optional[str] = None,
        min_rating: float = 0.0,
        budget: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 24,
        offset: int = 0,
        sort: str = "rating",
    ) -> dict:
        """Browse/filter restaurants for the Zomato-style search UI."""
        if not self._ready:
            raise RuntimeError(
                self._load_error or "Application is still loading restaurant data."
            )

        from src.phase2_input.filter_engine import FilterEngine
        from src.phase2_input.validator import validate_preferences

        budget_value = budget or "medium"
        prefs = validate_preferences(
            {
                "location": location,
                "budget": budget_value,
                "cuisine": cuisine,
                "min_rating": min_rating,
            }
        )
        engine = FilterEngine(self._repository, max_candidates=500)
        filter_result = engine.filter(prefs)
        restaurants = list(filter_result.candidates)

        if query:
            needle = query.strip().lower()
            if needle:
                restaurants = [
                    r
                    for r in restaurants
                    if needle in r.name.lower()
                    or any(needle in c.lower() for c in r.cuisines)
                    or needle in (r.area or "").lower()
                ]

        if sort == "cost_asc":
            restaurants.sort(
                key=lambda r: (r.cost_for_two is None, r.cost_for_two or 10**9, -r.rating)
            )
        elif sort == "cost_desc":
            restaurants.sort(
                key=lambda r: (r.cost_for_two is None, -(r.cost_for_two or 0), -r.rating)
            )
        elif sort == "name":
            restaurants.sort(key=lambda r: r.name.lower())
        else:
            restaurants.sort(key=lambda r: (-r.rating, -r.votes, r.name.lower()))

        total = len(restaurants)
        page = restaurants[offset : offset + limit]

        return {
            "total": total,
            "location": prefs.location,
            "message": filter_result.message,
            "restaurants": [
                {
                    "id": r.id,
                    "name": r.name,
                    "cuisine": ", ".join(r.cuisines) if r.cuisines else "N/A",
                    "cuisines": r.cuisines,
                    "rating": r.rating,
                    "votes": r.votes,
                    "estimated_cost": r.cost_display,
                    "cost_for_two": r.cost_for_two,
                    "area": r.area,
                    "location": r.location,
                    "address": r.address,
                    "rest_type": r.rest_type,
                    "budget_tier": r.budget_tier.value if r.budget_tier else None,
                }
                for r in page
            ],
        }

    def get_restaurant(self, restaurant_id: str) -> Optional[dict]:
        if not self._ready:
            return None
        for restaurant in self._repository.get_all():
            if restaurant.id == restaurant_id:
                return {
                    "id": restaurant.id,
                    "name": restaurant.name,
                    "cuisine": (
                        ", ".join(restaurant.cuisines) if restaurant.cuisines else "N/A"
                    ),
                    "cuisines": restaurant.cuisines,
                    "rating": restaurant.rating,
                    "votes": restaurant.votes,
                    "estimated_cost": restaurant.cost_display,
                    "cost_for_two": restaurant.cost_for_two,
                    "area": restaurant.area,
                    "location": restaurant.location,
                    "address": restaurant.address,
                    "rest_type": restaurant.rest_type,
                    "budget_tier": (
                        restaurant.budget_tier.value if restaurant.budget_tier else None
                    ),
                }
        return None

    def localities(self, location: str, *, limit: int = 12) -> list[dict]:
        """Popular areas within a city for the home page."""
        if not self._ready:
            return []
        from collections import Counter
        from src.phase1_data.preprocessor import normalize_location_name

        target = normalize_location_name(location).lower()
        counts: Counter[str] = Counter()
        for restaurant in self._repository.get_all():
            if restaurant.location.lower() == target and restaurant.area:
                counts[restaurant.area] += 1
        return [
            {"name": name, "count": count}
            for name, count in counts.most_common(limit)
        ]

