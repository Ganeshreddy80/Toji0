"""Strategy Framework models for TOJI V1."""

from __future__ import annotations

from typing import Dict, Any, List
from pydantic import BaseModel


class StrategyMetadata(BaseModel):
    """Metadata parameters of a composed strategy."""
    strategy_id: str
    name: str
    strategy_type: str  # "TREND_FOLLOWING", "MEAN_REVERSION", "AI", etc.
    version: str
    parameters: Dict[str, Any]


class ComposedStrategy(BaseModel):
    """Composed strategy blueprint ready for deployment."""
    metadata: StrategyMetadata
    symbols: List[str]
    active: bool = True
