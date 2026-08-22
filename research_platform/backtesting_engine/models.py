"""Immutable Pydantic models for the Event-Driven Backtesting Engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SlippageModel(BaseModel):
    """Slippage parameters container."""

    type: str  # Fixed, Percentage, ATR, Volume
    params: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class CommissionModel(BaseModel):
    """Commission parameters container."""

    type: str  # Fixed, Percentage
    params: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class MarginModel(BaseModel):
    """Margin ratios container."""

    initial_margin_pct: float = 0.50
    maintenance_margin_pct: float = 0.30

    model_config = ConfigDict(frozen=True)


class SimulationClock(BaseModel):
    """Monotonic discrete time simulator clock."""

    current_time: datetime
    step_ms: int = 1000

    model_config = ConfigDict(frozen=True)


class BacktestConfiguration(BaseModel):
    """Setup settings for execution simulations."""

    strategy_id: str
    dataset_id: str
    initial_capital: float
    start_time: datetime
    end_time: datetime
    slippage: SlippageModel
    commission: CommissionModel
    margin: MarginModel = Field(default_factory=MarginModel)

    model_config = ConfigDict(frozen=True)


class MarketEvent(BaseModel):
    """Historical quote, tick, or bar replay event."""

    timestamp: datetime
    symbol: str
    event_type: str  # OHLCV, Quote, Tick
    data: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class SignalEvent(BaseModel):
    """Strategy decision signal triggers."""

    timestamp: datetime
    strategy_id: str
    symbol: str
    direction: str  # BUY, SELL, HOLD
    signal_type: str
    values: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class OrderRequest(BaseModel):
    """Broker order submission contract."""

    order_id: str
    strategy_id: str
    symbol: str
    direction: str  # BUY, SELL
    quantity: float
    order_type: str  # MARKET, LIMIT, STOP, STOP_LIMIT
    price: float = 0.0
    time_in_force: str = "GTC"  # GTC, IOC, FOK

    model_config = ConfigDict(frozen=True)


class Order(BaseModel):
    """Broker execution tracking order status."""

    order_id: str
    request: OrderRequest
    status: str = "SUBMITTED"  # SUBMITTED, ACCEPTED, FILLED, REJECTED, CANCELLED
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    created_time: datetime
    updated_time: datetime

    model_config = ConfigDict(frozen=True)


class OrderFill(BaseModel):
    """Transaction fill details."""

    order_id: str
    fill_id: str
    symbol: str
    quantity: float
    price: float
    commission: float
    slippage: float
    timestamp: datetime

    model_config = ConfigDict(frozen=True)


class Trade(BaseModel):
    """Closed or executed trade details."""

    trade_id: str
    order_id: str
    symbol: str
    direction: str
    quantity: float
    price: float
    realized_pnl: float
    commission: float
    slippage: float
    timestamp: datetime

    model_config = ConfigDict(frozen=True)


class Position(BaseModel):
    """Multi-asset position holdings."""

    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    margin_requirement: float

    model_config = ConfigDict(frozen=True)


class PortfolioState(BaseModel):
    """Account capital balance snapshot."""

    timestamp: datetime
    cash: float
    equity: float
    margin: float
    buying_power: float
    positions: Dict[str, Position] = Field(default_factory=dict)
    realized_pnl: float
    unrealized_pnl: float

    model_config = ConfigDict(frozen=True)


class CashLedger(BaseModel):
    """Audit ledger tracking capital transactions."""

    balance: float
    description: str
    timestamp: datetime

    model_config = ConfigDict(frozen=True)


class EquityCurve(BaseModel):
    """Rolling balance plot."""

    timestamp: datetime
    equity: float
    returns: float

    model_config = ConfigDict(frozen=True)


class DrawdownSeries(BaseModel):
    """Drawdown percentage plots."""

    timestamp: datetime
    drawdown: float

    model_config = ConfigDict(frozen=True)


class ExecutionStatistics(BaseModel):
    """Performance evaluation summaries."""

    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    cagr: float

    model_config = ConfigDict(frozen=True)


class BacktestSnapshot(BaseModel):
    """Simulated state backups."""

    snapshot_id: str
    portfolio_state: PortfolioState
    timestamp: datetime

    model_config = ConfigDict(frozen=True)


class BacktestResult(BaseModel):
    """Simulations outputs summaries."""

    run_id: str
    configuration: BacktestConfiguration
    stats: ExecutionStatistics
    report_json: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class BacktestRun(BaseModel):
    """Simulations wrapper tracking progress."""

    run_id: str
    configuration: BacktestConfiguration
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    result: Optional[BacktestResult] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)
