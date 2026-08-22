"""Immutable Pydantic models for the Institutional Paper Trading Foundation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PaperAccount(BaseModel):
    """A virtual trading account tracking balance, equity, and peak drawdown."""

    account_id: str
    base_currency: str = "USD"
    initial_balance: float
    cash: float
    equity: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    drawdown: float = 0.0

    model_config = ConfigDict(frozen=True)


class PaperPosition(BaseModel):
    """An open trading position tracking size, entry cost, and market valuations."""

    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    model_config = ConfigDict(frozen=True)


class PaperOrder(BaseModel):
    """An execution order tracked in the paper trading sandbox."""

    order_id: str
    strategy_id: str
    symbol: str
    quantity: float
    price: float  # Limit price, or 0.0 for MARKET
    order_type: str  # MARKET, LIMIT
    side: str  # BUY, SELL
    status: str = "PENDING"  # PENDING, FILLED, CANCELLED, REJECTED
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    executed_price: Optional[float] = None
    executed_quantity: float = 0.0

    model_config = ConfigDict(frozen=True)


class PaperExecutionSession(BaseModel):
    """An active sandbox paper trading session configuration."""

    session_id: str
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    status: str = "ACTIVE"  # ACTIVE, INACTIVE
    account: PaperAccount

    model_config = ConfigDict(frozen=True)


class TradeJournalEntry(BaseModel):
    """An execution review log entry recording quantitative/AI rationale."""

    entry_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    symbol: str
    quantity: float
    price: float
    side: str
    realized_pnl: float = 0.0
    rationale: str

    model_config = ConfigDict(frozen=True)
