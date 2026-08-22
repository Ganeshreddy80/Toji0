"""Institutional Execution Simulator models.

Extends execution_engine with order lifecycle, fill details, and quality scoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    SUBMITTED = "SUBMITTED"
    PARTIAL_FILLED = "PARTIAL_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class SimulatedFill(BaseModel):
    """Represents the result of a simulated order fill."""

    order_id: str
    symbol: str
    side: str                   # BUY / SELL
    expected_price: float       # signal price at decision time
    fill_price: float           # actual execution price with spread + slippage
    quantity: float
    quantity_filled: float      # may differ from quantity for partial fills
    status: OrderStatus
    maker_fee: float            # fee for passive fills
    taker_fee: float            # fee for aggressive fills (market orders)
    fee_paid: float             # actual fee deducted
    slippage: float             # absolute price difference from expected
    slippage_cost: float        # slippage * quantity_filled in USDT
    after_fee_pnl: float        # net PnL after all costs
    fill_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""

    model_config = ConfigDict(frozen=True)


class ExecutionQualityReport(BaseModel):
    """Analytics card generated after each fill."""

    order_id: str
    symbol: str
    expected_price: float
    actual_fill: float
    slippage_abs: float
    slippage_pct: float
    fee_usdt: float
    liquidity_check: str        # PASS / FAIL
    risk_check: str             # PASS / FAIL
    execution_score: float      # 0–100
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
