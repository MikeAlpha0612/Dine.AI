"""Phase 2 input and filtering tests."""

from __future__ import annotations

import pytest

from src.data.models import Budget, Restaurant
from src.data.repository import RestaurantRepository
from src.input.exceptions import InputValidationError
from src.input.filter_engine import FilterEngine
from src.input.schemas import UserPreference
from src.input.validator import validate_preferences
from tests.fixtures.sample_rows import SAMPLE_ROWS


def _make_repo() -> RestaurantRepository:
    repo = RestaurantRepository()
    repo.load_from_rows(SAMPLE_ROWS)
    return repo


class TestValidatePreferences:
    def test_valid_minimal_input(self) -> None:
        prefs = validate_preferences({"location": "Bangalore", "budget": "medium"})
        assert prefs.location == "Bangalore"
        assert prefs.budget == Budget.MEDIUM
        assert prefs.min_rating == 0.0
        assert prefs.cuisine is None

    def test_valid_full_input(self) -> None:
        prefs = validate_preferences(
            {
                "location": "  Bangalore  ",
                "budget": "low",
                "cuisine": " Italian ",
                "min_rating": "4.0",
                "extra_preferences": "family-friendly",
            }
        )
        assert prefs.location == "Bangalore"
        assert prefs.cuisine == "Italian"
        assert prefs.min_rating == 4.0
        assert prefs.extra_preferences == "family-friendly"

    def test_missing_location(self) -> None:
        with pytest.raises(InputValidationError, match="Location is required"):
            validate_preferences({"budget": "low"})

    def test_whitespace_location(self) -> None:
        with pytest.raises(InputValidationError, match="Location is required"):
            validate_preferences({"location": "   ", "budget": "low"})

    def test_missing_budget(self) -> None:
        with pytest.raises(InputValidationError, match="Budget is required"):
            validate_preferences({"location": "Bangalore"})

    def test_invalid_budget(self) -> None:
        with pytest.raises(InputValidationError, match="low, medium, high"):
            validate_preferences({"location": "Bangalore", "budget": "cheap"})

    def test_invalid_min_rating_string(self) -> None:
        with pytest.raises(InputValidationError, match="Minimum rating"):
            validate_preferences(
                {"location": "Bangalore", "budget": "low", "min_rating": "4.0+"}
            )

    def test_invalid_min_rating_out_of_range(self) -> None:
        with pytest.raises(InputValidationError, match="between 0.0 and 5.0"):
            validate_preferences(
                {"location": "Bangalore", "budget": "low", "min_rating": 6.0}
            )

    def test_empty_cuisine_becomes_none(self) -> None:
        prefs = validate_preferences(
            {"location": "Bangalore", "budget": "low", "cuisine": "  "}
        )
        assert prefs.cuisine is None

    def test_truncates_long_extra_preferences(self) -> None:
        long_text = "x" * 600
        prefs = validate_preferences(
            {
                "location": "Bangalore",
                "budget": "low",
                "extra_preferences": long_text,
            }
        )
        assert prefs.extra_preferences is not None
        assert len(prefs.extra_preferences) == 500


class TestFilterEngine:
    @pytest.fixture
    def engine(self) -> FilterEngine:
        return FilterEngine(_make_repo())

    def test_returns_matching_candidates(self, engine: FilterEngine) -> None:
        prefs = UserPreference(location="Bangalore", budget=Budget.MEDIUM)
        result = engine.filter(prefs)

        assert not result.is_empty
        assert len(result.candidates) > 0
        assert all(r.location == "Bangalore" for r in result.candidates)

    def test_filters_by_cuisine(self, engine: FilterEngine) -> None:
        prefs = UserPreference(
            location="Bangalore",
            budget=Budget.MEDIUM,
            cuisine="Italian",
        )
        result = engine.filter(prefs)

        assert len(result.candidates) == 1
        assert result.candidates[0].name == "Onesta"

    def test_filters_by_min_rating(self, engine: FilterEngine) -> None:
        prefs = UserPreference(
            location="Bangalore",
            budget=Budget.HIGH,
            min_rating=4.0,
        )
        result = engine.filter(prefs)

        assert all(r.rating >= 4.0 for r in result.candidates)

    def test_unknown_location_empty_message(self, engine: FilterEngine) -> None:
        prefs = UserPreference(location="Goa", budget=Budget.LOW)
        result = engine.filter(prefs)

        assert result.is_empty
        assert result.message is not None
        assert "Goa" in result.message
        assert "Available cities" in result.message

    def test_strict_filters_empty_message(self, engine: FilterEngine) -> None:
        prefs = UserPreference(
            location="Bangalore",
            budget=Budget.LOW,
            cuisine="Sushi",
            min_rating=4.5,
        )
        result = engine.filter(prefs)

        assert result.is_empty
        assert result.message is not None
        assert "No restaurants match" in result.message
        assert "cuisine" in result.message

    def test_location_alias(self, engine: FilterEngine) -> None:
        prefs = UserPreference(location="bengaluru", budget=Budget.MEDIUM)
        result = engine.filter(prefs)

        assert not result.is_empty

    def test_candidates_sorted_by_rating(self, engine: FilterEngine) -> None:
        prefs = UserPreference(location="Bangalore", budget=Budget.HIGH)
        result = engine.filter(prefs)

        ratings = [r.rating for r in result.candidates]
        assert ratings == sorted(ratings, reverse=True)

    def test_caps_candidates(self) -> None:
        restaurants = [
            Restaurant(
                id=f"id-{i}",
                name=f"Restaurant {i}",
                location="Bangalore",
                area="Area",
                cuisines=["North Indian"],
                cost_for_two=600,
                cost_display="600",
                budget_tier=Budget.MEDIUM,
                rating=4.0 + i * 0.01,
                votes=i,
            )
            for i in range(40)
        ]
        repo = RestaurantRepository()
        repo.load_from_restaurants(restaurants)
        engine = FilterEngine(repo, max_candidates=10)

        prefs = UserPreference(location="Bangalore", budget=Budget.MEDIUM)
        result = engine.filter(prefs)

        assert len(result.candidates) == 10
        assert result.total_matched == 40
        assert result.is_capped
        assert result.message is not None
        assert "top 10" in result.message

    def test_single_candidate(self, engine: FilterEngine) -> None:
        prefs = UserPreference(
            location="Bangalore",
            budget=Budget.MEDIUM,
            cuisine="Italian",
        )
        result = engine.filter(prefs)

        assert len(result.candidates) == 1
        assert not result.is_capped

    def test_excludes_unknown_budget(self, engine: FilterEngine) -> None:
        prefs = UserPreference(location="Bangalore", budget=Budget.LOW)
        result = engine.filter(prefs)

        assert all(r.name != "Unknown Cost Cafe" for r in result.candidates)

    def test_location_with_qualifier(self, engine: FilterEngine) -> None:
        prefs = UserPreference(location="Banashankari, Bangalore", budget=Budget.MEDIUM)
        result = engine.filter(prefs)

        assert not result.is_empty

    def test_preserves_extra_preferences(self, engine: FilterEngine) -> None:
        prefs = UserPreference(
            location="Bangalore",
            budget=Budget.MEDIUM,
            extra_preferences="family-friendly",
        )
        result = engine.filter(prefs)

        assert result.preferences.extra_preferences == "family-friendly"


class TestFilterEngineIntegration:
    @pytest.mark.integration
    def test_filter_real_data_sample(self) -> None:
        repo = RestaurantRepository()
        repo.load(max_rows=500, use_cache=True)
        engine = FilterEngine(repo)

        raw = validate_preferences(
            {
                "location": "Bangalore",
                "budget": "medium",
                "min_rating": 3.5,
            }
        )
        result = engine.filter(raw)

        assert result.total_matched >= 0
        assert len(result.candidates) <= 25
        if result.candidates:
            assert all(r.rating >= 3.5 for r in result.candidates)
