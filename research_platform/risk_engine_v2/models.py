"""Risk Engine V2 models."""

from __future__ import annotations

from typing import Dict, List
from pydantic import BaseModel


class CorrelationResult(BaseModel):
    """Calculated asset correlation matrix updates."""
    assets: List[str]
    matrix: List[List[float]]


class PortfolioDrawdown(BaseModel):
    """Drawdown statistics for risk monitoring."""
    daily_drawdown: float
    weekly_drawdown: float
    max_drawdown: float
    limit_breached: bool
