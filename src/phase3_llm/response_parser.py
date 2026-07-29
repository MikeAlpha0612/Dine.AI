"""Parse and validate raw LLM JSON responses."""

from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError

from src.phase3_llm.exceptions import LLMResponseParseError
from src.phase3_llm.schemas import LLMResponse

logger = logging.getLogger(__name__)

_FENCE_PATTERN = re.compile(
    r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers if present."""
    stripped = text.strip()
    match = _FENCE_PATTERN.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def parse_llm_response(raw: str) -> LLMResponse:
    """
    Parse raw LLM output into a validated LLMResponse.

    Raises:
        LLMResponseParseError: If JSON is invalid or schema validation fails.
    """
    cleaned = strip_markdown_fences(raw)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMResponseParseError(
            f"LLM response is not valid JSON: {exc.msg}"
        ) from exc

    try:
        response = LLMResponse.model_validate(data)
    except ValidationError as exc:
        raise LLMResponseParseError(
            f"LLM response failed schema validation: {exc.errors()[0]['msg']}"
        ) from exc

    if not response.recommendations:
        raise LLMResponseParseError("LLM returned an empty recommendations list.")

    # Normalize duplicate or missing ranks
    seen_ranks: set[int] = set()
    normalized = []
    for index, item in enumerate(
        sorted(response.recommendations, key=lambda r: r.rank),
        start=1,
    ):
        rank = item.rank if item.rank not in seen_ranks else index
        seen_ranks.add(rank)
        normalized.append(item.model_copy(update={"rank": rank}))

    return response.model_copy(update={"recommendations": normalized})
