"""Immutable Pydantic models for the Execution Simulator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple
from pydantic import BaseModel, ConfigDict, Field


class SimulatedFill(BaseModel):
    """A simulated partial fill execution."""

    price: float
    quantity: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class SimulatedExecution(BaseModel):
    """A completed simulated execution details report."""

    execution_id: str
    order_id: str
    fills: List[SimulatedFill] = Field(default_factory=list)
    average_price: float
    slippage: float
    fees: float
    status: str = "FILLED"  # FILLED, PARTIAL, REJECTED

    model_config = ConfigDict(frozen=True)


class OrderBookSlice(BaseModel):
    """An L2 orderbook slice snapshot."""

    asks: List[Tuple[float, float]] = Field(default_factory=list)  # (price, size)
    bids: List[Tuple[float, float]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
