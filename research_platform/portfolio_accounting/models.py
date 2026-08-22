"""Pydantic models for the Portfolio Accounting subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


PositionSide = Literal["LONG", "SHORT"]
HistoryEventType = Literal["OPEN", "UPDATE", "PARTIAL_CLOSE", "CLOSE"]


class ValuatedPosition(BaseModel):
    """Full position valuation record updated on every market tick."""

    symbol: str
    side: PositionSide
    quantity: float
    average_entry: float
    current_price: float
    market_value: float = 0.0          # quantity * current_price
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    pnl_percent: float = 0.0           # unrealized_pnl / (avg_entry * qty) * 100
    highest_price_seen: float = 0.0
    lowest_price_seen: float = float("inf")
    max_favorable_excursion: float = 0.0   # MFE: best unrealized gain ever
    max_adverse_excursion: float = 0.0     # MAE: worst unrealized loss ever
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_update: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=False)  # mutable — updated on ticks

    def tick_update(self, price: float) -> None:
        """Apply a new market price and recompute all derived fields."""
        self.current_price = price
        self.market_value = self.quantity * price
        self.last_update = datetime.now(timezone.utc)

        if price > self.highest_price_seen:
            self.highest_price_seen = price
        if price < self.lowest_price_seen:
            self.lowest_price_seen = price

        cost_basis = self.average_entry * self.quantity
        if self.side == "LONG":
            self.unrealized_pnl = (price - self.average_entry) * self.quantity
            mfe_pnl = (self.highest_price_seen - self.average_entry) * self.quantity
            mae_pnl = (self.lowest_price_seen - self.average_entry) * self.quantity
        else:
            self.unrealized_pnl = (self.average_entry - price) * self.quantity
            mfe_pnl = (self.average_entry - self.lowest_price_seen) * self.quantity
            mae_pnl = (self.average_entry - self.highest_price_seen) * self.quantity

        self.max_favorable_excursion = max(0.0, mfe_pnl)
        self.max_adverse_excursion = min(0.0, mae_pnl)

        if cost_basis != 0.0:
            self.pnl_percent = (self.unrealized_pnl / abs(cost_basis)) * 100.0


class PortfolioSnapshot(BaseModel):
    """Immutable point-in-time portfolio state."""

    snapshot_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Cash & equity
    cash_balance: float = 0.0
    reserved_margin: float = 0.0
    portfolio_value: float = 0.0       # cash + open positions market value
    equity: float = 0.0               # portfolio_value - reserved_margin
    buying_power: float = 0.0         # available cash for new positions

    # PnL
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    daily_pnl: float = 0.0

    # Costs
    fees: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0

    # Positions
    open_position_count: int = 0
    total_exposure: float = 0.0        # sum of all market values

    model_config = ConfigDict(frozen=True)


class TradeRecord(BaseModel):
    """Completed trade record stored in the trade journal."""

    trade_id: str
    symbol: str
    side: str                          # BUY (opening leg)
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    holding_duration_seconds: float = 0.0

    # Results
    realized_pnl: float = 0.0
    return_pct: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    net_pnl: float = 0.0               # realized_pnl - commission - slippage

    # Context
    strategy: str = ""
    ai_confidence: float = 0.0
    risk_approved: bool = True
    portfolio_decision: str = "APPROVED"
    rationale: str = ""
    reason_closed: str = "SIGNAL"      # SIGNAL, STOP_LOSS, TAKE_PROFIT, MANUAL

    model_config = ConfigDict(frozen=True)


class PositionHistoryEntry(BaseModel):
    """Single event in a position's lifecycle timeline."""

    entry_id: str
    symbol: str
    event_type: HistoryEventType
    quantity_delta: float = 0.0        # + open/add, - reduce/close
    quantity_remaining: float = 0.0
    price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class PortfolioMetrics(BaseModel):
    """Continuously computed portfolio performance metrics."""

    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    total_return_pct: float = 0.0
    win_rate: float = 0.0
    average_winner: float = 0.0
    average_loser: float = 0.0
    profit_factor: float = 0.0         # gross profit / gross loss
    expectancy: float = 0.0            # (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    largest_winner: float = 0.0
    largest_loser: float = 0.0
    current_exposure: float = 0.0      # total market value of open positions
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # Phase 16 additionals
    loss_rate: float = 0.0
    sortino_ratio: float = 0.0
    daily_return: float = 0.0
    monthly_return: float = 0.0
    equity_curve: List[float] = Field(default_factory=list)
    rolling_volatility: float = 0.0
    rolling_returns: float = 0.0

    model_config = ConfigDict(frozen=True)


class TradeLedgerEntry(BaseModel):
    """Immutable ledger entry representing a transaction/fill."""
    trade_id: str
    order_id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    commission: float
    slippage: float
    realized_pnl: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
