"""Strategy Engine data models."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass
class StrategyMetadata:
    name: str
    version: str
    description: str
    author: str

@dataclass
class TradeIdea:
    symbol: str
    direction: str  # "LONG", "SHORT", "FLAT"
    confidence: float  # [0.0, 1.0]
    reason: str
    timestamp: datetime
    risk_notes: str

@dataclass
class StrategyResult:
    strategy_name: str
    trade_ideas: list[TradeIdea]
    execution_duration_ms: float
    success: bool
    error_message: str | None = None
