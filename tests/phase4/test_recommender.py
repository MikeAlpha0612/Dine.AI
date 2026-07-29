"""Phase 4 recommendation engine tests."""

from __future__ import annotations

import json

import pytest

from src.phase1_data.models import Budget, Restaurant
from src.phase1_data.repository import RestaurantRepository
from src.phase4_engine.parser import parse_llm_json
from src.phase4_engine.ranker import (
    default_explanation,
    fallback_recommendations,
    match_restaurant,
    merge_llm_with_candidates,
)
from src.phase4_engine.recommender import Recommender
from src.phase2_input.schemas import UserPreference
from src.phase3_llm.client import MockLLMClient
from src.phase3_llm.exceptions import LLMError, LLMResponseParseError
from src.phase3_llm.schemas import LLMRecommendationItem, LLMResponse
from tests.phase1.fixtures.sample_rows import SAMPLE_ROWS


def _prefs(**overrides) -> UserPreference:
    data = {
        "location": "Bangalore",
        "budget": Budget.MEDIUM,
        "cuisine": None,
        "min_rating": 0.0,
        "extra_preferences": None,
    }
    data.update(overrides)
    return UserPreference(**data)


def _candidates() -> list[Restaurant]:
    return [
        Restaurant(
            id="1",
            name="Onesta",
            location="Bangalore",
            area="Banashankari",
            cuisines=["Pizza", "Italian"],
            cost_for_two=600,
            cost_display="600",
            budget_tier=Budget.MEDIUM,
            rating=4.6,
            votes=2556,
        ),
        Restaurant(
            id="2",
            name="Jalsa",
            location="Bangalore",
            area="Banashankari",
            cuisines=["North Indian", "Chinese"],
            cost_for_two=800,
            cost_display="800",
            budget_tier=Budget.MEDIUM,
            rating=4.1,
            votes=775,
        ),
        Restaurant(
            id="3",
            name="Addhuri Udupi Bhojana",
            location="Bangalore",
            area="Banashankari",
            cuisines=["South Indian"],
            cost_for_two=300,
            cost_display="300",
            budget_tier=Budget.LOW,
            rating=3.7,
            votes=88,
        ),
    ]


def _repo() -> RestaurantRepository:
    repo = RestaurantRepository()
    repo.load_from_rows(SAMPLE_ROWS)
    return repo


VALID_LLM_JSON = json.dumps(
    {
        "recommendations": [
            {
                "name": "Onesta",
                "rank": 1,
                "explanation": "Great Italian pick for medium budget.",
            },
            {
                "name": "Jalsa",
                "rank": 2,
                "explanation": "Solid North Indian option nearby.",
            },
        ],
        "summary": "Top medium-budget picks in Bangalore.",
    }
)


class TestParser:
    def test_parse_valid_json(self) -> None:
        result = parse_llm_json(VALID_LLM_JSON)
        assert len(result.recommendations) == 2

    def test_parse_invalid_raises(self) -> None:
        with pytest.raises(LLMResponseParseError):
            parse_llm_json("not json")


class TestRanker:
    def test_exact_match(self) -> None:
        matched = match_restaurant("Onesta", _candidates())
        assert matched is not None
        assert matched.name == "Onesta"

    def test_fuzzy_match(self) -> None:
        matched = match_restaurant("Onestaa", _candidates())
        assert matched is not None
        assert matched.name == "Onesta"

    def test_hallucination_dropped(self) -> None:
        assert match_restaurant("Fake Restaurant XYZ", _candidates()) is None

    def test_merge_enriches_fields(self) -> None:
        llm = LLMResponse(
            recommendations=[
                LLMRecommendationItem(
                    name="Onesta",
                    rank=1,
                    explanation="Best Italian pick.",
                )
            ],
            summary="Summary",
        )
        results = merge_llm_with_candidates(llm, _candidates(), _prefs(), top_n=2)

        assert results[0].name == "Onesta"
        assert results[0].cuisine == "Pizza, Italian"
        assert results[0].rating == 4.6
        assert results[0].estimated_cost == "600"
        assert results[0].explanation == "Best Italian pick."
        assert results[0].rank == 1

    def test_merge_drops_hallucinations_and_backfills(self) -> None:
        llm = LLMResponse(
            recommendations=[
                LLMRecommendationItem(name="Hallucinated Place", rank=1, explanation="x"),
                LLMRecommendationItem(name="Onesta", rank=2, explanation="real"),
            ]
        )
        results = merge_llm_with_candidates(llm, _candidates(), _prefs(), top_n=3)

        names = [r.name for r in results]
        assert "Hallucinated Place" not in names
        assert "Onesta" in names
        assert len(results) == 3
        assert all(r.rank == i for i, r in enumerate(results, start=1))

    def test_merge_deduplicates(self) -> None:
        llm = LLMResponse(
            recommendations=[
                LLMRecommendationItem(name="Onesta", rank=1, explanation="first"),
                LLMRecommendationItem(name="Onesta", rank=2, explanation="dup"),
            ]
        )
        results = merge_llm_with_candidates(llm, _candidates(), _prefs(), top_n=2)
        assert [r.name for r in results].count("Onesta") == 1

    def test_merge_caps_at_top_n(self) -> None:
        llm = LLMResponse(
            recommendations=[
                LLMRecommendationItem(name="Onesta", rank=1, explanation="a"),
                LLMRecommendationItem(name="Jalsa", rank=2, explanation="b"),
                LLMRecommendationItem(
                    name="Addhuri Udupi Bhojana", rank=3, explanation="c"
                ),
            ]
        )
        results = merge_llm_with_candidates(llm, _candidates(), _prefs(), top_n=2)
        assert len(results) == 2

    def test_missing_explanation_uses_template(self) -> None:
        llm = LLMResponse(
            recommendations=[
                LLMRecommendationItem(name="Onesta", rank=1, explanation="  "),
            ]
        )
        results = merge_llm_with_candidates(llm, _candidates(), _prefs(), top_n=1)
        assert "Bangalore" in results[0].explanation
        assert "medium" in results[0].explanation

    def test_fallback_recommendations(self) -> None:
        results = fallback_recommendations(_candidates(), _prefs(), top_n=2)
        assert len(results) == 2
        assert results[0].rank == 1
        assert results[0].name == "Onesta"

    def test_default_explanation(self) -> None:
        text = default_explanation(_candidates()[0], _prefs())
        assert "Italian" in text or "Pizza" in text


class TestRecommender:
    def test_end_to_end_with_mock_llm(self) -> None:
        client = MockLLMClient(lambda _: VALID_LLM_JSON)
        recommender = Recommender(_repo(), client, top_n=2)

        result = recommender.recommend(
            {
                "location": "Bangalore",
                "budget": "medium",
                "cuisine": "Italian",
            }
        )

        assert not result.is_empty
        assert not result.used_fallback
        assert result.recommendations[0].name == "Onesta"
        assert result.recommendations[0].rating == 4.6
        assert result.summary is not None

    def test_empty_filter_result(self) -> None:
        client = MockLLMClient(lambda _: VALID_LLM_JSON)
        recommender = Recommender(_repo(), client)

        result = recommender.recommend(
            {"location": "Goa", "budget": "low"}
        )

        assert result.is_empty
        assert result.message is not None
        assert "Goa" in result.message

    def test_llm_failure_uses_fallback(self) -> None:
        class FailingClient(MockLLMClient):
            def recommend(self, preferences, candidates, *, top_n=5):
                raise LLMError("provider down")

        recommender = Recommender(_repo(), FailingClient(lambda _: ""), top_n=3)
        result = recommender.recommend(
            {"location": "Bangalore", "budget": "medium"}
        )

        assert not result.is_empty
        assert result.used_fallback
        assert result.message is not None
        assert "AI summary unavailable" in result.message
        assert all(r.explanation for r in result.recommendations)

    def test_no_llm_client_uses_fallback(self) -> None:
        recommender = Recommender(_repo(), llm_client=None, top_n=2)
        result = recommender.recommend(
            {"location": "Bangalore", "budget": "medium"}
        )

        assert not result.is_empty
        assert result.used_fallback

    def test_accepts_user_preference_object(self) -> None:
        recommender = Recommender(_repo(), llm_client=None, top_n=1)
        result = recommender.recommend(_prefs(budget=Budget.MEDIUM))
        assert len(result.recommendations) == 1

    def test_hallucinated_only_llm_response_backfills(self) -> None:
        hallucinated = json.dumps(
            {
                "recommendations": [
                    {"name": "Totally Fake Cafe", "rank": 1, "explanation": "nope"}
                ],
                "summary": "bad",
            }
        )
        client = MockLLMClient(lambda _: hallucinated)
        recommender = Recommender(_repo(), client, top_n=2)
        result = recommender.recommend(
            {"location": "Bangalore", "budget": "medium", "cuisine": "Italian"}
        )

        assert not result.is_empty
        assert all(r.name != "Totally Fake Cafe" for r in result.recommendations)
        assert len(result.recommendations) == 1  # only Onesta matches Italian medium
