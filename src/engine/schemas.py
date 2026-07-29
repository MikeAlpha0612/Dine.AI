"""Output schemas for the recommendation engine."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.input.schemas import UserPreference


class Recommendation(BaseModel):
    """A single enriched restaurant recommendation."""

    rank: int = Field(ge=1)
    name: str
    cuisine: str
    rating: float
    estimated_cost: str
    explanation: str
    restaurant_id: Optional[str] = None
    area: Optional[str] = None

    model_config = {"frozen": True}


class RecommendationResult(BaseModel):
    """Final output of the recommendation pipeline."""

    recommendations: list[Recommendation]
    summary: Optional[str] = None
    preferences: UserPreference
    used_fallback: bool = False
    message: Optional[str] = None

    model_config = {"frozen": True}

    @property
    def is_empty(self) -> bool:
        return len(self.recommendations) == 0
