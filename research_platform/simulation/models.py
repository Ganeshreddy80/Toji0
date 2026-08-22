"""Immutable Pydantic models for the Digital Twin & Simulation Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ReplayMode(str, Enum):
    MARKET = "MARKET"
    ORDER = "ORDER"
    STRATEGY = "STRATEGY"
    PORTFOLIO = "PORTFOLIO"


class SimTick(BaseModel):
    """A simulated asset price feed tick detail record."""

    price: float
    volume: float
    spread: float = 0.001
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class SimOrder(BaseModel):
    """A simulated trade order executed on the simulator exchange."""

    order_id: str
    strategy_id: str
    symbol: str
    quantity: float
    price: float
    order_type: str  # MARKET, LIMIT
    side: str  # BUY, SELL
    status: str = "PENDING"  # PENDING, FILLED, REJECTED
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class StressParameters(BaseModel):
    """Stress testing simulation parameters."""

    volatility_multiplier: float = 1.0
    spread_scale: float = 1.0
    network_latency_ms: float = 0.0

    model_config = ConfigDict(frozen=True)


class ReplayConfiguration(BaseModel):
    """Configuration params representing a simulation replay run details."""

    session_id: str
    start_time: datetime
    end_time: datetime
    strategy_ids: List[str]
    mode: ReplayMode = ReplayMode.MARKET
    stress_params: StressParameters = Field(default_factory=StressParameters)

    model_config = ConfigDict(frozen=True)


class SimulationResult(BaseModel):
    """Statistical summary metrics resulting from a simulation execution run."""

    session_id: str
    total_trades: int
    total_pnl: float
    max_drawdown: float
    replication_error: float  # Variance error comparing simulated vs real outputs
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
