"""Abstract contracts for the Backtesting Engine.
"""

from __future__ import annotations

import abc
from typing import List, Optional

from research_platform.backtesting_engine.models import (
    BacktestRun,
    Order,
    OrderFill,
    OrderRequest,
    PortfolioState,
    MarketEvent
)


class IBacktestRepository(abc.ABC):
    """Abstract database repository contract for backtesting persistence."""

    @abc.abstractmethod
    def save_run(self, run: BacktestRun) -> None:
        """Persist a BacktestRun."""

    @abc.abstractmethod
    def get_run(self, run_id: str) -> Optional[BacktestRun]:
        """Fetch BacktestRun by ID."""

    @abc.abstractmethod
    def list_runs(self) -> List[BacktestRun]:
        """List all runs."""


class IMatchingEngine(abc.ABC):
    """Abstract contract for transaction matching."""

    @abc.abstractmethod
    def match_orders(self, orders: List[Order], market_data: MarketEvent) -> List[OrderFill]:
        """Process and match pending orders against current market event prices."""


class IExecutionSimulator(abc.ABC):
    """Abstract contract for realistic trade execution parameters."""

    @abc.abstractmethod
    def simulate_fill(self, request: OrderRequest, market_data: MarketEvent) -> OrderFill:
        """Apply spread, slippage, and commissions calculations to simulate fills."""


class IPortfolioTracker(abc.ABC):
    """Abstract contract for tracking multi-asset position balances."""

    @abc.abstractmethod
    def process_fill(self, fill: OrderFill) -> PortfolioState:
        """Update cash, realized PnL, margin requirements, and position lists."""

    @abc.abstractmethod
    def mark_to_market(self, market_data: MarketEvent) -> PortfolioState:
        """Recalculate unrealized PnL and total equity curves."""
