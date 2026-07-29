"""Phase 3 LLM integration tests."""

from __future__ import annotations

import json
import os

import pytest

from src.data.models import Budget, Restaurant
from src.input.schemas import UserPreference
from src.llm.client import LLMClient, MockLLMClient
from src.llm.config import LLMConfig
from src.llm.exceptions import (
    LLMAuthError,
    LLMEmptyCandidatesError,
    LLMResponseParseError,
)
from src.llm.prompt_builder import build_prompt, serialize_candidates
from src.llm.response_parser import parse_llm_response, strip_markdown_fences
from src.llm.schemas import PromptPayload


def _sample_preferences() -> UserPreference:
    return UserPreference(
        location="Bangalore",
        budget=Budget.MEDIUM,
        cuisine="Italian",
        min_rating=4.0,
        extra_preferences="family-friendly",
    )


def _sample_candidates() -> list[Restaurant]:
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
            rest_type="Casual Dining",
        ),
        Restaurant(
            id="2",
            name='McDonald\'s & "Grill"',
            location="Bangalore",
            area="Indiranagar",
            cuisines=["Fast Food"],
            cost_for_two=400,
            cost_display="400",
            budget_tier=Budget.LOW,
            rating=4.2,
            votes=500,
        ),
    ]


VALID_LLM_JSON = json.dumps(
    {
        "recommendations": [
            {
                "name": "Onesta",
                "rank": 1,
                "explanation": "Top-rated Italian option within medium budget.",
            }
        ],
        "summary": "Best Italian pick in Bangalore.",
    }
)


class TestPromptBuilder:
    def test_build_prompt_contains_preferences(self) -> None:
        payload = build_prompt(_sample_preferences(), _sample_candidates())
        assert "Bangalore" in payload.user_prompt
        assert "medium" in payload.user_prompt
        assert "Italian" in payload.user_prompt
        assert "family-friendly" in payload.user_prompt

    def test_serialize_candidates_valid_json(self) -> None:
        raw = serialize_candidates(_sample_candidates())
        data = json.loads(raw)
        assert len(data) == 2
        assert data[0]["name"] == "Onesta"

    def test_special_characters_in_json(self) -> None:
        raw = serialize_candidates(_sample_candidates())
        assert 'McDonald\'s & "Grill"' in raw or "McDonald" in raw
        json.loads(raw)  # must not raise

    def test_to_messages(self) -> None:
        payload = build_prompt(_sample_preferences(), _sample_candidates())
        messages = payload.to_messages()
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"


class TestResponseParser:
    def test_parse_valid_response(self) -> None:
        result = parse_llm_response(VALID_LLM_JSON)
        assert len(result.recommendations) == 1
        assert result.recommendations[0].name == "Onesta"
        assert result.summary == "Best Italian pick in Bangalore."

    def test_parse_markdown_fenced_json(self) -> None:
        fenced = f"```json\n{VALID_LLM_JSON}\n```"
        result = parse_llm_response(fenced)
        assert result.recommendations[0].name == "Onesta"

    def test_strip_markdown_fences(self) -> None:
        assert strip_markdown_fences("```json\n{}\n```") == "{}"

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(LLMResponseParseError, match="not valid JSON"):
            parse_llm_response("not json at all")

    def test_empty_recommendations_raises(self) -> None:
        with pytest.raises(LLMResponseParseError, match="empty recommendations"):
            parse_llm_response('{"recommendations": [], "summary": "none"}')

    def test_normalizes_duplicate_ranks(self) -> None:
        raw = json.dumps(
            {
                "recommendations": [
                    {"name": "A", "rank": 1, "explanation": "x"},
                    {"name": "B", "rank": 1, "explanation": "y"},
                ]
            }
        )
        result = parse_llm_response(raw)
        ranks = [r.rank for r in result.recommendations]
        assert ranks == [1, 2]


class _FakeCompleter:
    """Fake OpenAI completer for retry/error tests."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls = 0

    def create(self, **kwargs) -> object:
        self.calls += 1
        action = self._responses.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = type("Msg", (), {"content": content})()


class TestLLMClient:
    def test_recommend_with_mock_client(self) -> None:
        client = MockLLMClient(lambda _: VALID_LLM_JSON)
        result = client.recommend(_sample_preferences(), _sample_candidates())
        assert result.recommendations[0].name == "Onesta"

    def test_empty_candidates_raises(self) -> None:
        client = MockLLMClient(lambda _: VALID_LLM_JSON)
        with pytest.raises(LLMEmptyCandidatesError):
            client.recommend(_sample_preferences(), [])

    def test_parse_retry_on_invalid_then_valid(self) -> None:
        responses = ["not json", VALID_LLM_JSON]
        client = MockLLMClient(lambda _: responses.pop(0))
        result = client.recommend(_sample_preferences(), _sample_candidates())
        assert result.recommendations[0].name == "Onesta"

    def test_auth_error_no_retry(self) -> None:
        from openai import APIStatusError
        from unittest.mock import MagicMock

        config = LLMConfig(api_key="bad-key")
        real_error = APIStatusError.__new__(APIStatusError)
        real_error.status_code = 401
        real_error.message = "Unauthorized"
        real_error.body = None
        real_error.request = MagicMock()
        real_error.response = MagicMock(status_code=401)

        completer = _FakeCompleter([real_error])
        client = LLMClient(config, completer=completer)

        with pytest.raises(LLMAuthError):
            client.complete(PromptPayload(system_prompt="s", user_prompt="u"))

        assert completer.calls == 1

    def test_retries_on_server_error(self) -> None:
        from openai import APIStatusError
        from unittest.mock import MagicMock

        config = LLMConfig(api_key="key", max_retries=3)
        server_error = APIStatusError.__new__(APIStatusError)
        server_error.status_code = 500
        server_error.message = "Server Error"
        server_error.body = None
        server_error.request = MagicMock()
        server_error.response = MagicMock(status_code=500)

        ok = type(
            "Resp",
            (),
            {
                "choices": [
                    _FakeChoice(
                        '{"recommendations":[{"name":"Onesta","rank":1,"explanation":"x"}]}'
                    )
                ]
            },
        )()
        completer = _FakeCompleter([server_error, server_error, ok])
        client = LLMClient(config, completer=completer)

        raw = client.complete(PromptPayload(system_prompt="s", user_prompt="u"))
        assert "Onesta" in raw
        assert completer.calls == 3


class TestLLMConfig:
    def test_from_env_missing_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="GROQ_API_KEY"):
            LLMConfig.from_env()

    def test_from_env_with_groq_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
        config = LLMConfig.from_env()
        assert config.api_key == "gsk-test"
        assert "groq.com" in config.base_url
        assert "llama" in config.model

    def test_from_env_fallback_openai_key_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "gsk-compat")
        config = LLMConfig.from_env()
        assert config.api_key == "gsk-compat"


@pytest.mark.integration
def test_live_llm_recommendation() -> None:
    """Call Groq when GROQ_API_KEY (or OPENAI_API_KEY) is configured."""
    if not (os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")):
        pytest.skip("GROQ_API_KEY not set")

    client = LLMClient.from_env()
    result = client.recommend(_sample_preferences(), _sample_candidates(), top_n=2)

    assert len(result.recommendations) >= 1
    assert result.recommendations[0].explanation
