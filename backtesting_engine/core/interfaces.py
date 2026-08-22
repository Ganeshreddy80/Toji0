"""Abstract interfaces for the Backtesting Engine (Sprint 7A)."""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Any, Dict, List, Optional

from backtesting_engine.core.enums import (
    OrderType,
    PositionSide,
    ReplayStatus,
    SimulatedOrderStatus,
    TimeInForce,
)
from backtesting_engine.core.models import (
    BacktestConfig,
    BacktestResult,
    EquityPoint,
    MarketBar,
    SimulatedFill,
    SimulatedOrder,
    TradeRecord,
)


class IHistoricalReplayEngine(abc.ABC):
    """Protocol for historical bar replay and timestamp stepping."""

    @abc.abstractmethod
    def load_data(self, bars: List[MarketBar]) -> None:
        """Load historical bar data into the replay queue."""

    @abc.abstractmethod
    def start(self) -> None:
        """Start or resume replay."""

    @abc.abstractmethod
    def pause(self) -> None:
        """Pause replay."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop replay and reset state."""

    @abc.abstractmethod
    def step(self) -> Optional[MarketBar]:
        """Replay next single bar synchronously."""

    @abc.abstractmethod
    def seek(self, timestamp: datetime) -> bool:
        """Seek replay cursor to target timestamp."""

    @property
    @abc.abstractmethod
    def status(self) -> ReplayStatus:
        """Return current replay status."""


class ISimulatedBroker(abc.ABC):
    """Protocol for managing simulated broker orders and state transitions."""

    @abc.abstractmethod
    def place_order(
        self,
        symbol: str,
        side: PositionSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: float = 0.0,
        stop_price: float = 0.0,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ) -> SimulatedOrder:
        """Place a new simulated broker order."""

    @abc.abstractmethod
    def cancel_order(self, order_id: str) -> Optional[SimulatedOrder]:
        """Cancel an active simulated order."""

    @abc.abstractmethod
    def get_order(self, order_id: str) -> Optional[SimulatedOrder]:
        """Get an order by ID."""

    @abc.abstractmethod
    def list_orders(self, status: Optional[SimulatedOrderStatus] = None) -> List[SimulatedOrder]:
        """List active or historical simulated orders."""


class IOrderMatchingEngine(abc.ABC):
    """Protocol for deterministic order matching against replayed market data."""

    @abc.abstractmethod
    def match_orders(
        self,
        orders: List[SimulatedOrder],
        bar: MarketBar,
        config: BacktestConfig,
    ) -> List[SimulatedFill]:
        """Match open orders against current market bar and return executed fills."""


class ITradeLedger(abc.ABC):
    """Protocol for tracking open and closed trade positions and PnL accounting."""

    @abc.abstractmethod
    def process_fill(self, fill: SimulatedFill, current_bar: MarketBar) -> TradeRecord:
        """Process a fill, updating open position or creating a closed trade record."""

    @abc.abstractmethod
    def update_unrealized_pnl(self, current_bar: MarketBar) -> float:
        """Update mark-to-market unrealized PnL for open positions against current bar."""

    @abc.abstractmethod
    def get_open_trades(self) -> List[TradeRecord]:
        """Retrieve all currently open trade positions."""

    @abc.abstractmethod
    def get_closed_trades(self) -> List[TradeRecord]:
        """Retrieve all closed trade records."""


class IEquityEngine(abc.ABC):
    """Protocol for tracking account balance, equity, drawdowns, and return series."""

    @abc.abstractmethod
    def update(self, current_bar: MarketBar, ledger: ITradeLedger) -> EquityPoint:
        """Update account equity snapshot for the current replayed bar."""

    @abc.abstractmethod
    def get_returns_series(self) -> List[float]:
        """Return deterministic periodic returns series for Research Platform."""

    @abc.abstractmethod
    def get_equity_curve(self) -> List[float]:
        """Return deterministic account equity curve points for Research Platform."""

    @abc.abstractmethod
    def get_snapshots(self) -> List[EquityPoint]:
        """Retrieve all equity snapshot points."""


class IBacktestRepository(abc.ABC):
    """Protocol for persisting backtest configurations, sessions, trades, orders, and results."""

    @abc.abstractmethod
    def save_result(self, result: BacktestResult) -> None:
        """Persist a backtest result atomically."""

    @abc.abstractmethod
    def load_result(self, backtest_id: str) -> Optional[BacktestResult]:
        """Load a backtest result by ID."""

    @abc.abstractmethod
    def list_results(self) -> List[BacktestResult]:
        """List all persisted backtest results."""


class IBacktestOrchestrator(abc.ABC):
    """Authoritative protocol for orchestrating end-to-end backtest execution."""

    @abc.abstractmethod
    def run_backtest(
        self,
        config: BacktestConfig,
        bars: List[MarketBar],
        orders_to_place: Optional[List[Dict[str, Any]]] = None,
    ) -> BacktestResult:
        """Execute an event-driven backtest pipeline end-to-end."""
