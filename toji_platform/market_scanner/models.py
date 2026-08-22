"""Market Scanner data models."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass
class MarketMetrics:
    atr: float
    volatility: float
    rsi: float
    relative_volume: float  # Current volume / average historical volume
    spread: float
    liquidity_depth: float
    time_since_last_update_sec: float

@dataclass
class MarketScan:
    symbol: str
    timestamp: datetime
    market_states: list[str]  # E.g. ["TRENDING_UP", "HIGH_VOLATILITY"]
    metrics: MarketMetrics
    confidence_score: float  # Data confidence metric [0.0, 1.0]
    quality_score: float     # Market quality metric [0.0, 1.0]
    diagnostics: dict[str, Any]
