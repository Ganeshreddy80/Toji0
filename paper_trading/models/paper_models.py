"""Immutable Pydantic V2 data models for the Paper Trading subsystem (Sprint 9A)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class PaperOrderStatus(str, Enum):
    """Paper order execution status states."""

    NEW = "NEW"
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class PaperSessionStatus(str, Enum):
    """Paper trading session lifecycle states."""

    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


class PaperOrderSide(str, Enum):
    """Order transaction side."""

    BUY = "BUY"
    SELL = "SELL"
    LONG = "LONG"
    SHORT = "SHORT"


class PaperOrderType(str, Enum):
    """Order execution type."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class PaperAccount(BaseModel):
    """Immutable snapshot representation of a paper trading account ledger."""

    account_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Account UUID.")
    starting_cash: float = Field(..., ge=0.0, description="Initial starting cash balance.")
    available_cash: float = Field(..., ge=0.0, description="Unreserved cash balance available for trading.")
    reserved_cash: float = Field(default=0.0, ge=0.0, description="Cash reserved for open limit orders.")
    buying_power: float = Field(..., ge=0.0, description="Total purchasing power.")
    equity: float = Field(..., description="Total account equity (cash + position mark-to-market).")
    realized_pnl: float = Field(default=0.0, description="Cumulative realized profit and loss.")
    unrealized_pnl: float = Field(default=0.0, description="Current unrealized profit and loss across open positions.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Account creation timestamp.",
    )

    model_config = ConfigDict(frozen=True)


class PaperPosition(BaseModel):
    """Immutable representation of an open asset position in paper trading."""

    symbol: str = Field(..., description="Target asset trading pair / symbol.")
    quantity: float = Field(..., description="Position size quantity (positive for long, negative for short).")
    average_price: float = Field(..., ge=0.0, description="Volume-weighted average entry price.")
    market_price: float = Field(..., ge=0.0, description="Current mark-to-market price.")
    market_value: float = Field(..., description="Total mark-to-market position value.")
    unrealized_pnl: float = Field(default=0.0, description="Unrealized profit/loss for position.")
    realized_pnl: float = Field(default=0.0, description="Cumulative realized profit/loss from closed portions.")

    model_config = ConfigDict(frozen=True)


class PaperOrder(BaseModel):
    """Immutable representation of a simulated broker order."""

    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique order UUID.")
    symbol: str = Field(..., description="Asset symbol.")
    side: PaperOrderSide = Field(..., description="Order side (BUY/SELL).")
    quantity: float = Field(..., gt=0.0, description="Requested order quantity.")
    order_type: PaperOrderType = Field(default=PaperOrderType.MARKET, description="Order execution type.")
    limit_price: float = Field(default=0.0, ge=0.0, description="Target limit price for LIMIT orders.")
    stop_price: float = Field(default=0.0, ge=0.0, description="Target trigger price for STOP orders.")
    status: PaperOrderStatus = Field(default=PaperOrderStatus.NEW, description="Order status.")
    filled_quantity: float = Field(default=0.0, ge=0.0, description="Cumulative filled quantity.")
    average_fill_price: float = Field(default=0.0, ge=0.0, description="Cumulative average fill price.")
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Order submission timestamp.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last status update timestamp.",
    )

    model_config = ConfigDict(frozen=True)


class PaperTrade(BaseModel):
    """Immutable execution record for a filled paper order."""

    trade_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique trade execution UUID.")
    order_id: str = Field(..., description="Associated paper order ID.")
    symbol: str = Field(..., description="Asset symbol.")
    quantity: float = Field(..., gt=0.0, description="Executed trade fill quantity.")
    fill_price: float = Field(..., gt=0.0, description="Executed fill price.")
    commission: float = Field(default=0.0, ge=0.0, description="Incurred commission fee.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Fill execution timestamp.",
    )

    model_config = ConfigDict(frozen=True)


class PaperSession(BaseModel):
    """Immutable specification and status for a active paper trading session."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Session UUID.")
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Session start timestamp.",
    )
    status: PaperSessionStatus = Field(default=PaperSessionStatus.STOPPED, description="Session state.")
    account: PaperAccount = Field(..., description="Associated paper account state.")

    model_config = ConfigDict(frozen=True)
