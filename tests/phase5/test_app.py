"""Phase 5 UI and API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.phase5_app.api import routes as routes_mod
from src.phase5_app.api.routes import create_app
from src.phase5_app.main import build_parser, main as cli_main
from src.phase5_app.service import AppService
from src.phase5_app.ui.forms import validate_form
from src.phase5_app.ui.results import (
    format_cost,
    format_meta_line,
    format_rating,
    format_recommendation_card,
    truncate_explanation,
)
from src.phase1_data.repository import RestaurantRepository
from src.phase4_engine.recommender import Recommender
from src.phase4_engine.schemas import Recommendation
from tests.phase1.fixtures.sample_rows import SAMPLE_ROWS


def _ready_service() -> AppService:
    repo = RestaurantRepository()
    repo.load_from_rows(SAMPLE_ROWS)
    service = AppService(use_llm=False, top_n=2)
    service._repository = repo
    service._recommender = Recommender(repo, None, top_n=2)
    service._ready = True
    return service


class TestFormatters:
    def test_format_rating(self) -> None:
        assert format_rating(4.666) == "4.7"
        assert format_rating(0.0) == "New / Unrated"

    def test_format_cost(self) -> None:
        assert format_cost("600") == "₹600 for two"
        assert format_cost("unknown") == "Cost not available"
        assert format_cost(None) == "Cost not available"

    def test_truncate_explanation(self) -> None:
        short, truncated = truncate_explanation("Hello")
        assert short == "Hello"
        assert not truncated

        long_text = "x" * 400
        preview, truncated = truncate_explanation(long_text, max_length=50)
        assert truncated
        assert len(preview) <= 50

    def test_format_meta_line_omits_empty_cuisine(self) -> None:
        rec = Recommendation(
            rank=1,
            name="Cafe",
            cuisine="N/A",
            rating=4.0,
            estimated_cost="500",
            explanation="Nice place",
        )
        line = format_meta_line(rec)
        assert "N/A" not in line
        assert "★ 4.0" in line
        assert "₹500" in line

    def test_format_recommendation_card(self) -> None:
        rec = Recommendation(
            rank=1,
            name="Onesta",
            cuisine="Italian",
            rating=4.6,
            estimated_cost="600",
            explanation="Great pick",
            area="Banashankari",
        )
        card = format_recommendation_card(rec)
        assert "#1  Onesta" in card
        assert "Italian" in card
        assert "Great pick" in card


class TestForms:
    def test_valid_form(self) -> None:
        payload, error = validate_form(location="Bangalore", budget="medium")
        assert error is None
        assert payload is not None
        assert payload["location"] == "Bangalore"

    def test_invalid_location(self) -> None:
        payload, error = validate_form(location="  ", budget="low")
        assert payload is None
        assert error is not None
        assert "Location" in error


class TestCLI:
    def test_parser_requires_location_and_budget(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args([])
        assert exc.value.code == 2

    def test_cli_parse_ok(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["--location", "Bangalore", "--budget", "medium", "--no-llm"]
        )
        assert args.location == "Bangalore"
        assert args.no_llm is True

    def test_cli_end_to_end_no_llm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = _ready_service()

        def fake_load(self: AppService) -> None:
            self._repository = service._repository
            self._recommender = service._recommender
            self._ready = True

        monkeypatch.setattr(AppService, "load", fake_load)
        code = cli_main(
            [
                "--location",
                "Bangalore",
                "--budget",
                "medium",
                "--cuisine",
                "Italian",
                "--no-llm",
            ]
        )
        assert code == 0


class TestAPI:
    def test_malformed_body_returns_422(self) -> None:
        app = create_app(use_llm=False, skip_startup_load=True)
        with TestClient(app) as client:
            routes_mod._service = _ready_service()
            response = client.post("/recommend", json={"location": "x"})
            assert response.status_code == 422

    def test_invalid_budget_returns_422(self) -> None:
        app = create_app(use_llm=False, skip_startup_load=True)
        with TestClient(app) as client:
            routes_mod._service = _ready_service()
            response = client.post(
                "/recommend",
                json={"location": "Bangalore", "budget": "cheap"},
            )
            assert response.status_code == 422

    def test_recommend_success(self) -> None:
        app = create_app(use_llm=False, skip_startup_load=True)
        with TestClient(app) as client:
            routes_mod._service = _ready_service()
            response = client.post(
                "/recommend",
                json={
                    "location": "Bangalore",
                    "budget": "medium",
                    "cuisine": "Italian",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["recommendations"]) >= 1
            assert data["recommendations"][0]["name"] == "Onesta"
            assert data["recommendations"][0]["explanation"]

    def test_health(self) -> None:
        app = create_app(use_llm=False, skip_startup_load=True)
        with TestClient(app) as client:
            routes_mod._service = _ready_service()
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
