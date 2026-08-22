"""Immutable Pydantic models for Portfolio Construction.
"""

from __future__ import annotations

from typing import Dict, List
from pydantic import BaseModel, ConfigDict, Field


class PortfolioAllocation(BaseModel):
    """Allocated weights maps for capital sizing."""

    allocation_id: str
    weights: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class RebalanceOrder(BaseModel):
    """Rebalance orders detail changes."""

    symbol: str
    target_weight: float
    current_weight: float
    order_side: str  # BUY, SELL, HOLD

    model_config = ConfigDict(frozen=True)


class CorrelationMatrix(BaseModel):
    """Assets correlation matrices."""

    assets: List[str] = Field(default_factory=list)
    matrix: List[List[float]] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)
