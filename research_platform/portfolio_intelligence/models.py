"""Portfolio Intelligence models."""

from __future__ import annotations

from typing import Dict
from pydantic import BaseModel


class PortfolioPerformanceMetrics(BaseModel):
    """Calculated metrics for portfolio performance assessment."""
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    alpha: float
    beta: float


class RebalanceInstruction(BaseModel):
    """Instruction set generated to rebalance asset weights."""
    target_weights: Dict[str, float]
    volatility_target: float
