"""User preference and filter result schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.phase1_data.models import Budget, Restaurant


class UserPreference(BaseModel):
    """Validated user preferences for restaurant recommendations."""

    location: str = Field(..., min_length=1, description="City, e.g. Bangalore")
    budget: Budget
    cuisine: Optional[str] = Field(default=None, description="Partial cuisine match")
    min_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    extra_preferences: Optional[str] = Field(
        default=None,
        description="Free-text preferences, e.g. family-friendly",
    )

    model_config = {"frozen": True}


class FilterResult(BaseModel):
    """Outcome of filtering restaurants against user preferences."""

    candidates: list[Restaurant]
    total_matched: int
    is_capped: bool
    message: Optional[str] = None
    preferences: UserPreference

    model_config = {"frozen": True}

    @property
    def is_empty(self) -> bool:
        return len(self.candidates) == 0
