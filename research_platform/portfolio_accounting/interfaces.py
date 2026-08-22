"""Abstract contracts for the Portfolio Accounting subsystem."""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional


class IPositionValuationEngine(abc.ABC):
    @abc.abstractmethod
    def on_tick(self, symbol: str, price: float) -> Optional[Any]:
        """Update a single position's valuation on a market price tick."""

    @abc.abstractmethod
    def on_fill(self, symbol: str, side: str, quantity: float, price: float, commission: float) -> Any:
        """Open or extend a position after a confirmed fill."""

    @abc.abstractmethod
    def on_close(self, symbol: str, quantity: float, exit_price: float, commission: float) -> Optional[Any]:
        """Reduce or fully close a position; return realized PnL."""

    @abc.abstractmethod
    def get_all_positions(self) -> List[Any]:
        """Return all currently open ValuatedPositions."""


class IPortfolioAccountingEngine(abc.ABC):
    @abc.abstractmethod
    def recalculate(self, positions: List[Any]) -> Any:
        """Recompute and return a fresh PortfolioSnapshot."""

    @abc.abstractmethod
    def apply_fill(self, side: str, quantity: float, price: float, commission: float, slippage: float) -> None:
        """Adjust cash/fees ledger after a fill."""

    @abc.abstractmethod
    def get_snapshot(self) -> Any:
        """Return the most recent PortfolioSnapshot."""


class IMetricsEngine(abc.ABC):
    @abc.abstractmethod
    def ingest_trade(self, trade: Any) -> None:
        """Feed a completed TradeRecord for metrics computation."""

    @abc.abstractmethod
    def compute(self, initial_balance: float, current_equity: float, positions: List[Any]) -> Any:
        """Recompute and return PortfolioMetrics."""


class ITradeJournal(abc.ABC):
    @abc.abstractmethod
    def record(self, trade: Any) -> None:
        """Persist a completed TradeRecord."""

    @abc.abstractmethod
    def get_all(self) -> List[Any]:
        """Return all journal entries."""
