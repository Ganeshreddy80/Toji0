"""Immutable Pydantic models for the Live Trading Engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LiveTradingSession(BaseModel):
    """Execution session details wrapper."""

    session_id: str
    status: str  # ACTIVE, PAUSED, TERMINATED
    start_time: datetime
    end_time: Optional[datetime] = None

    model_config = ConfigDict(frozen=True)


class TradingState(BaseModel):
    """Current state registers holding margins and counts."""

    state_id: str
    available_cash: float
    total_equity: float
    margin_utilization: float

    model_config = ConfigDict(frozen=True)


class OpenPosition(BaseModel):
    """Active open position details."""

    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    model_config = ConfigDict(frozen=True)


class ClosedPosition(BaseModel):
    """Archived closed position history details."""

    symbol: str
    quantity: float
    entry_price: float
    exit_price: float
    realized_pnl: float
    closed_time: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class LiveOrder(BaseModel):
    """Currently active order in exchange books."""

    order_id: str
    symbol: str
    quantity: float
    price: float
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class ActiveSignal(BaseModel):
    """Signal currently evaluated by the processors."""

    signal_id: str
    symbol: str
    direction: str  # BUY, SELL
    strength: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class PendingSignal(BaseModel):
    """Signal waiting execution queue spaces."""

    signal_id: str
    symbol: str
    direction: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class ExecutionContext(BaseModel):
    """Details about system environment parameters."""

    mode: str = "LIVE"  # LIVE, PAPER
    exchange_name: str
    account_id: str

    model_config = ConfigDict(frozen=True)


class TradingCalendar(BaseModel):
    """Trading sessions calendars."""

    calendar_id: str
    timezone: str = "UTC"
    market_holidays: List[datetime] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class MarketSession(BaseModel):
    """Segment details about current session limits."""

    session_id: str
    market_name: str
    is_open: bool

    model_config = ConfigDict(frozen=True)


class SessionMetrics(BaseModel):
    """Performance ratios tracked during session limits."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_ratio: float
    profit_factor: float

    model_config = ConfigDict(frozen=True)


class HeartbeatStatus(BaseModel):
    """Heartbeat response check values."""

    heartbeat_id: str
    status: str  # ALIVE, TIMEOUT
    latency_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class RecoveryCheckpoint(BaseModel):
    """Checkpoint profiles saved for restart recover checks."""

    checkpoint_id: str
    session_id: str
    open_positions: List[OpenPosition] = Field(default_factory=list)
    pending_orders: List[LiveOrder] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class TradingSnapshot(BaseModel):
    """High-level snapshot wrapper."""

    snapshot_id: str
    state: TradingState
    open_positions: List[OpenPosition]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)
