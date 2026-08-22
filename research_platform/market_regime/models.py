"""Immutable Pydantic models for the Market Regime Intelligence Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RegimeType(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGEBOUND = "RANGEBOUND"


class VolatilityRegime(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class LiquidityRegime(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class MarketRegime(BaseModel):
    """The global detected market regime context state."""

    symbol: str
    regime_type: RegimeType
    volatility: VolatilityRegime
    liquidity: LiquidityRegime
    confidence_score: float = 1.0
    features: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class MarketStructure(BaseModel):
    """Structural market levels, order blocks and breakout configurations."""

    symbol: str
    support_levels: List[float] = Field(default_factory=list)
    resistance_levels: List[float] = Field(default_factory=list)
    breakouts: List[str] = Field(default_factory=list)
    order_blocks: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class RegimeTransition(BaseModel):
    """Details of a regime shift transition event."""

    symbol: str
    old_regime: Optional[MarketRegime] = None
    new_regime: MarketRegime
    probability: float = 1.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class HistoricalRegimeRecord(BaseModel):
    """Historical timeline log record for regime lookups."""

    record_id: str
    symbol: str
    regime: MarketRegime
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
