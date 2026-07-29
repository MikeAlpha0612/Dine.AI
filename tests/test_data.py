"""Phase 1 data layer tests."""

from __future__ import annotations

import pytest

from src.data.exceptions import RepositoryNotReadyError
from src.data.models import Budget, FilterCriteria
from src.data.preprocessor import (
    cost_to_budget_tier,
    extract_city_from_address,
    normalize_location_name,
    parse_cost,
    parse_cuisines,
    parse_rating,
    preprocess_row,
    preprocess_rows,
)
from src.data.repository import RestaurantRepository
from tests.fixtures.sample_rows import SAMPLE_ROWS


class TestPreprocessor:
    def test_parse_rating_valid(self) -> None:
        assert parse_rating("4.1/5") == 4.1

    def test_parse_rating_missing(self) -> None:
        assert parse_rating("-") == 0.0
        assert parse_rating("NEW") == 0.0
        assert parse_rating(None) == 0.0

    def test_parse_rating_clamped(self) -> None:
        assert parse_rating("6.5/5") == 5.0

    def test_parse_cost_single_value(self) -> None:
        cost, display = parse_cost("800")
        assert cost == 800
        assert display == "800"

    def test_parse_cost_range(self) -> None:
        cost, display = parse_cost("300-500")
        assert cost == 400
        assert display == "300-500"

    def test_parse_cost_unknown(self) -> None:
        cost, display = parse_cost(None)
        assert cost is None
        assert display == "unknown"

    def test_parse_cuisines(self) -> None:
        assert parse_cuisines("North Indian, Mughlai, Chinese") == [
            "North Indian",
            "Mughlai",
            "Chinese",
        ]

    def test_cost_to_budget_tier(self) -> None:
        assert cost_to_budget_tier(300) == Budget.LOW
        assert cost_to_budget_tier(600) == Budget.MEDIUM
        assert cost_to_budget_tier(900) == Budget.HIGH
        assert cost_to_budget_tier(None) is None

    def test_normalize_location_aliases(self) -> None:
        assert normalize_location_name("bengaluru") == "Bangalore"
        assert normalize_location_name("  delhi ") == "New Delhi"

    def test_extract_city_from_address(self) -> None:
        assert extract_city_from_address("942, Banashankari, Bangalore") == "Bangalore"
        assert extract_city_from_address("Gali Kababian, Jama Masjid, New Delhi") == "New Delhi"

    def test_preprocess_row_skips_missing_name(self) -> None:
        row = SAMPLE_ROWS[-3]  # empty name
        assert preprocess_row(row) is None

    def test_preprocess_rows_deduplicates_by_rating(self) -> None:
        restaurants = preprocess_rows(SAMPLE_ROWS)
        names = [r.name for r in restaurants if r.name == "Duplicate Place"]
        assert names == ["Duplicate Place"]
        duplicate = next(r for r in restaurants if r.name == "Duplicate Place")
        assert duplicate.rating == 4.2


class TestRestaurantRepository:
    @pytest.fixture
    def repo(self) -> RestaurantRepository:
        repository = RestaurantRepository()
        repository.load_from_rows(SAMPLE_ROWS)
        return repository

    def test_not_ready_raises(self) -> None:
        repository = RestaurantRepository()
        with pytest.raises(RepositoryNotReadyError):
            repository.get_all()

    def test_get_all(self, repo: RestaurantRepository) -> None:
        assert repo.count == 6  # 8 rows - 1 invalid - 1 deduped

    def test_filter_by_location(self, repo: RestaurantRepository) -> None:
        criteria = FilterCriteria(location="Bangalore")
        results = repo.filter_by(criteria)
        assert len(results) >= 4
        assert all(r.location == "Bangalore" for r in results)

    def test_filter_by_location_alias(self, repo: RestaurantRepository) -> None:
        criteria = FilterCriteria(location="bengaluru")
        results = repo.filter_by(criteria)
        assert len(results) >= 4

    def test_filter_by_cuisine(self, repo: RestaurantRepository) -> None:
        criteria = FilterCriteria(location="Bangalore", cuisine="Italian")
        results = repo.filter_by(criteria)
        assert len(results) == 1
        assert results[0].name == "Onesta"

    def test_filter_by_min_rating(self, repo: RestaurantRepository) -> None:
        criteria = FilterCriteria(location="Bangalore", min_rating=4.0)
        results = repo.filter_by(criteria)
        assert all(r.rating >= 4.0 for r in results)

    def test_filter_by_budget(self, repo: RestaurantRepository) -> None:
        criteria = FilterCriteria(location="Bangalore", budget=Budget.LOW)
        results = repo.filter_by(criteria)
        assert all(r.budget_tier == Budget.LOW for r in results)

    def test_filter_excludes_unknown_budget(self, repo: RestaurantRepository) -> None:
        criteria = FilterCriteria(location="Bangalore", budget=Budget.MEDIUM)
        results = repo.filter_by(criteria)
        assert all(r.name != "Unknown Cost Cafe" for r in results)

    def test_filter_sort_order(self, repo: RestaurantRepository) -> None:
        criteria = FilterCriteria(location="Bangalore")
        results = repo.filter_by(criteria)
        ratings = [r.rating for r in results]
        assert ratings == sorted(ratings, reverse=True)

    def test_get_locations(self, repo: RestaurantRepository) -> None:
        locations = repo.get_locations()
        assert "Bangalore" in locations
        assert "New Delhi" in locations

    def test_get_cuisines(self, repo: RestaurantRepository) -> None:
        cuisines = repo.get_cuisines()
        assert "Italian" in cuisines
        assert "Mughlai" in cuisines


@pytest.mark.integration
def test_load_from_huggingface() -> None:
    """Integration test: load a small slice of the real dataset."""
    repository = RestaurantRepository()
    repository.load(max_rows=100, use_cache=True)

    assert repository.is_ready
    assert repository.count > 0

    locations = repository.get_locations()
    assert len(locations) > 0

    if "Bangalore" in locations:
        results = repository.filter_by(FilterCriteria(location="Bangalore"))
        assert len(results) > 0
        restaurant = results[0]
        assert restaurant.name
        assert restaurant.location
        assert isinstance(restaurant.cuisines, list)
