"""Domain models for restaurant data."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Budget(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Restaurant(BaseModel):
    """Normalized restaurant record from the Zomato dataset."""

    id: str
    name: str
    location: str  # city (e.g. Bangalore)
    area: str  # neighborhood from dataset location field
    cuisines: list[str]
    cost_for_two: Optional[int] = None
    cost_display: str = "unknown"
    budget_tier: Optional[Budget] = None
    rating: float = 0.0
    votes: int = 0
    rest_type: Optional[str] = None
    address: Optional[str] = None

    model_config = {"frozen": True}


class FilterCriteria(BaseModel):
    """Criteria for repository filtering (Phase 1 subset; extended in Phase 2)."""

    location: Optional[str] = None
    cuisine: Optional[str] = None
    min_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    budget: Optional[Budget] = None

    model_config = {"frozen": True}
