"""Structured schemas for LLM prompts and responses."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LLMRecommendationItem(BaseModel):
    """Single ranked recommendation returned by the LLM."""

    name: str
    rank: int = Field(ge=1)
    explanation: str


class LLMResponse(BaseModel):
    """
    Expected JSON shape from the LLM.

    Example:
        {
          "recommendations": [
            {"name": "Onesta", "rank": 1, "explanation": "..."}
          ],
          "summary": "Top Italian picks in Bangalore for your budget."
        }
    """

    recommendations: list[LLMRecommendationItem]
    summary: Optional[str] = None


class PromptPayload(BaseModel):
    """Structured prompt content sent to the LLM."""

    system_prompt: str
    user_prompt: str

    def to_messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt},
        ]
