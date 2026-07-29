"""Parse and validate LLM JSON for the recommendation engine."""

from __future__ import annotations

from src.llm.exceptions import LLMResponseParseError
from src.llm.response_parser import parse_llm_response as _parse_llm_response
from src.llm.schemas import LLMResponse


def parse_llm_json(raw: str) -> LLMResponse:
    """
    Parse raw LLM text into a validated LLMResponse.

    Raises:
        LLMResponseParseError: If the response is invalid or empty.
    """
    return _parse_llm_response(raw)


__all__ = ["LLMResponseParseError", "parse_llm_json"]
