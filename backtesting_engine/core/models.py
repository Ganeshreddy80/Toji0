"""Immutable Pydantic V2 models for the Backtesting Engine (Sprint 7A)."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backtesting_engine.core.enums import (
    CommissionModel,
    MarketImpactModel,
    OrderType,
    PositionSide,
    ReplayStatus,
    SimulatedOrderStatus,
    SlippageModel,
    SpreadModel,
    TimeInForce,
    TradeStatus,
)


class MarketBar(BaseModel):
    """Immutable representation of a historical OHLCV market bar for backtesting."""

    symbol: str = Field(default="BTC/USDT", description="Asset symbol.")
    timeframe: str = Field(default="1h", description="Timeframe interval.")
    timestamp: datetime = Field(..., description="Bar opening timestamp.")
    open: float = Field(..., gt=0.0, description="Open price.")
    high: float = Field(..., gt=0.0, description="High price.")
    low: float = Field(..., gt=0.0, description="Low price.")
    close: float = Field(..., gt=0.0, description="Close price.")
    volume: float = Field(default=0.0, ge=0.0, description="Volume.")
    index: int = Field(default=0, ge=0, description="Sequence index.")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_timezone(cls, v: datetime) -> datetime:
        """Enforce timezone-aware datetimes for market bars."""
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("MarketBar timestamp must be timezone-aware (e.g. UTC).")
        return v

    model_config = ConfigDict(frozen=True)


class SyntheticQuote(BaseModel):
    """Immutable synthetic bid/ask quote generated from market bar."""

    symbol: str = Field(..., description="Asset symbol.")
    bid: float = Field(..., gt=0.0, description="Synthetic bid price.")
    ask: float = Field(..., gt=0.0, description="Synthetic ask price.")
    mid: float = Field(..., gt=0.0, description="Synthetic mid price.")
    spread: float = Field(..., ge=0.0, description="Absolute spread value.")
    timestamp: datetime = Field(..., description="Quote timestamp.")

    model_config = ConfigDict(frozen=True)


class BacktestConfig(BaseModel):
    """Immutable configuration parameters for a historical backtest execution."""

    backtest_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Backtest UUID.")
    name: str = Field(default="Backtest Run", description="Human-readable name.")
    start_date: datetime = Field(..., description="Start boundary timestamp.")
    end_date: datetime = Field(..., description="End boundary timestamp.")
    initial_capital: float = Field(default=100000.0, gt=0.0, description="Starting account balance.")
    commission_rate: float = Field(default=0.001, ge=0.0, description="Commission percentage per trade (e.g. 0.001 = 0.1%).")
    slippage_model: str = Field(default="FIXED", description="Slippage model ('NONE', 'FIXED', 'FIXED_TICKS', 'FIXED_PERCENT', 'SPREAD_BASED', 'VOLUME_BASED').")
    slippage_value: float = Field(default=0.0, ge=0.0, description="Slippage value in absolute points, ticks, or percentage.")
    spread_model: str = Field(default="NONE", description="Spread model ('NONE', 'FIXED', 'PERCENTAGE', 'VOLATILITY_BASED').")
    spread_value: float = Field(default=0.0, ge=0.0, description="Spread value in price points or percentage.")
    max_volume_pct: float = Field(default=1.0, gt=0.0, le=1.0, description="Maximum executable fraction of bar volume [0.01, 1.0].")
    latency_bars: int = Field(default=0, ge=0, description="Execution delay in replay bars.")
    commission_model: str = Field(default="PERCENTAGE", description="Commission model ('FIXED', 'PERCENTAGE', 'MAKER_TAKER').")
    maker_commission_rate: float = Field(default=0.0005, ge=0.0, description="Maker fee rate.")
    taker_commission_rate: float = Field(default=0.0010, ge=0.0, description="Taker fee rate.")
    min_commission: float = Field(default=0.0, ge=0.0, description="Minimum commission fee floor.")
    max_commission: float = Field(default=0.0, ge=0.0, description="Maximum commission fee cap (0.0 = uncapped).")
    market_impact_model: str = Field(default="NONE", description="Market impact model ('NONE', 'LINEAR', 'SQUARE_ROOT').")
    market_impact_factor: float = Field(default=0.1, ge=0.0, description="Market impact multiplier coefficient.")
    min_quantity: float = Field(default=0.0001, gt=0.0, description="Minimum allowed order quantity.")
    max_quantity: float = Field(default=100000.0, gt=0.0, description="Maximum allowed order quantity.")
    lot_size: float = Field(default=0.0001, gt=0.0, description="Quantity increment lot size.")
    tick_size: float = Field(default=0.01, gt=0.0, description="Price increment tick size.")
    lot_precision: int = Field(default=4, ge=0, description="Quantity decimal precision.")
    tick_precision: int = Field(default=2, ge=0, description="Price decimal precision.")
    seed: int = Field(default=42, description="Random seed for deterministic replay.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional backtest parameters.")

    model_config = ConfigDict(frozen=True)


class ExecutionReport(BaseModel):
    """Immutable execution audit report for an order fill or execution event."""

    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Report UUID.")
    backtest_id: str = Field(..., description="Backtest UUID.")
    order_id: str = Field(..., description="Target order ID.")
    symbol: str = Field(..., description="Asset symbol.")
    side: PositionSide = Field(..., description="Position side.")
    requested_quantity: float = Field(..., gt=0.0, description="Initial order requested quantity.")
    executed_quantity: float = Field(..., ge=0.0, description="Executed fill quantity in this event.")
    remaining_quantity: float = Field(..., ge=0.0, description="Unfilled remaining quantity.")
    avg_fill_price: float = Field(..., ge=0.0, description="Cumulative average fill price.")
    slippage: float = Field(default=0.0, description="Applied price slippage.")
    commission: float = Field(default=0.0, ge=0.0, description="Incurred commission fee.")
    latency_bars: int = Field(default=0, ge=0, description="Execution delay in bars.")
    liquidity_restricted: bool = Field(default=False, description="True if fill was capped by bar volume limit.")
    status: SimulatedOrderStatus = Field(..., description="Resulting order status.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Execution timestamp.")

    model_config = ConfigDict(frozen=True)


class SimulatedOrder(BaseModel):
    """Immutable specification and status for a simulated broker order."""

    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique order ID.")
    symbol: str = Field(..., description="Target trading pair / asset symbol.")
    side: PositionSide = Field(..., description="LONG (Buy) or SHORT (Sell).")
    quantity: float = Field(..., gt=0.0, description="Order quantity.")
    price: float = Field(default=0.0, ge=0.0, description="Limit price for LIMIT and STOP_LIMIT orders.")
    stop_price: float = Field(default=0.0, ge=0.0, description="Trigger price for STOP and STOP_LIMIT orders.")
    order_type: OrderType = Field(default=OrderType.MARKET, description="Order execution type.")
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC, description="Time-in-force instruction.")
    status: SimulatedOrderStatus = Field(default=SimulatedOrderStatus.NEW, description="Order status.")
    filled_quantity: float = Field(default=0.0, ge=0.0, description="Cumulative filled quantity.")
    avg_fill_price: float = Field(default=0.0, ge=0.0, description="Average fill price.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Order creation timestamp.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp.")

    model_config = ConfigDict(frozen=True)


class SimulatedFill(BaseModel):
    """Immutable record of an executed order fill."""

    fill_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique fill ID.")
    order_id: str = Field(..., description="Associated order ID.")
    symbol: str = Field(..., description="Asset symbol.")
    side: PositionSide = Field(..., description="Fill side.")
    fill_quantity: float = Field(..., gt=0.0, description="Executed fill quantity.")
    fill_price: float = Field(..., gt=0.0, description="Executed fill price.")
    fee: float = Field(default=0.0, ge=0.0, description="Commission fee incurred.")
    slippage: float = Field(default=0.0, description="Applied price slippage.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Fill timestamp.")

    model_config = ConfigDict(frozen=True)


class TradeRecord(BaseModel):
    """Immutable history record of a position trade."""

    trade_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique trade ID.")
    order_id: str = Field(..., description="Associated order ID.")
    symbol: str = Field(..., description="Asset symbol.")
    side: PositionSide = Field(..., description="Position side.")
    entry_price: float = Field(..., gt=0.0, description="Average position entry price.")
    exit_price: Optional[float] = Field(default=None, description="Average position exit price if closed.")
    quantity: float = Field(..., gt=0.0, description="Trade position size.")
    commission: float = Field(default=0.0, ge=0.0, description="Total commission fees.")
    realized_pnl: float = Field(default=0.0, description="Realized profit and loss.")
    unrealized_pnl: float = Field(default=0.0, description="Unrealized profit and loss.")
    status: TradeStatus = Field(default=TradeStatus.OPEN, description="Trade status.")
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Trade open timestamp.")
    closed_at: Optional[datetime] = Field(default=None, description="Trade close timestamp.")

    model_config = ConfigDict(frozen=True)


class EquityPoint(BaseModel):
    """Immutable account equity snapshot point."""

    timestamp: datetime = Field(..., description="Snapshot timestamp.")
    balance: float = Field(..., description="Realized cash balance.")
    equity: float = Field(..., description="Total account equity (balance + open PnL).")
    drawdown: float = Field(default=0.0, ge=0.0, le=1.0, description="Peak-to-trough drawdown ratio [0.0, 1.0].")
    open_pnl: float = Field(default=0.0, description="Unrealized PnL across open trades.")
    closed_pnl: float = Field(default=0.0, description="Cumulative realized PnL.")
    account_value: float = Field(..., description="Total portfolio mark-to-market value.")

    model_config = ConfigDict(frozen=True)


class BacktestResult(BaseModel):
    """Immutable output result of a historical backtest run."""

    backtest_id: str = Field(..., description="Backtest UUID.")
    config: BacktestConfig = Field(..., description="Associated backtest configuration.")
    replay_session_id: str = Field(..., description="Replay session ID.")
    status: ReplayStatus = Field(default=ReplayStatus.COMPLETED, description="Replay execution status.")
    returns_series: List[float] = Field(default_factory=list, description="Periodic return series output for Research Platform.")
    equity_curve: List[float] = Field(default_factory=list, description="Account equity curve points output for Research Platform.")
    equity_snapshots: List[EquityPoint] = Field(default_factory=list, description="Detailed equity snapshots.")
    trades: List[TradeRecord] = Field(default_factory=list, description="All completed and open trade records.")
    fills: List[SimulatedFill] = Field(default_factory=list, description="All executed fill records.")
    final_equity: float = Field(default=0.0, description="Ending portfolio account value.")
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Completion timestamp.")
    error_message: Optional[str] = Field(default=None, description="Error message if failed.")

    model_config = ConfigDict(frozen=True)
