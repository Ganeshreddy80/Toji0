"""Pydantic schemas and structures for the backtesting engine."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class Order(BaseModel):
    """Pydantic model representing an order submitted to the simulator."""

    symbol: str = Field(...)
    qty: float = Field(..., gt=0.0, description="Absolute quantity to trade")
    side: str = Field(..., pattern="^(buy|sell)$")
    order_type: str = Field(default="market", pattern="^(market|limit)$")
    price: float | None = Field(default=None, description="Limit price for limit orders")
    timestamp: datetime = Field(...)


class Trade(BaseModel):
    """Pydantic model representing an executed trade recorded in the ledger."""

    trade_id: str = Field(...)
    symbol: str = Field(...)
    qty: float = Field(...)
    price: float = Field(...)
    side: str = Field(...)
    timestamp: datetime = Field(...)
    commission: float = Field(default=0.0)
    slippage: float = Field(default=0.0)
    realized_pnl: float = Field(default=0.0)


class Position(BaseModel):
    """Pydantic model representing an active asset position in the portfolio."""

    symbol: str = Field(...)
    qty: float = Field(..., description="Quantity held. Positive for long, negative for short")
    avg_entry_price: float = Field(..., gt=0.0)
    realized_pnl: float = Field(default=0.0)

    @property
    def is_long(self) -> bool:
        return self.qty > 0.0

    @property
    def is_short(self) -> bool:
        return self.qty < 0.0

    @property
    def absolute_qty(self) -> float:
        return abs(self.qty)


class PortfolioState(BaseModel):
    """Pydantic model representing the portfolio state at a specific snapshot in time."""

    timestamp: datetime = Field(...)
    cash: float = Field(...)
    holdings_value: float = Field(...)
    total_equity: float = Field(...)
