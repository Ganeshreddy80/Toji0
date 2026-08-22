"""Abstract contracts for the Market Data Integration & Paper Execution Synchronization.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional


class IMarketFeedRouter(abc.ABC):
    """Abstract contract for receiving and routing live market ticks."""

    @abc.abstractmethod
    def start_routing(self) -> None:
        """Start listening to event bus market data feeds."""

    @abc.abstractmethod
    def stop_routing(self) -> None:
        """Stop listening to event bus market data feeds."""


class IPaperExecutionRouter(abc.ABC):
    """Abstract contract for execution routing configurations."""

    @abc.abstractmethod
    def route_order(
        self,
        strategy_id: str,
        symbol: str,
        quantity: float,
        price: float,
        order_type: str,
        side: str,
        rationale: str
    ) -> Any:
        """Route order requests to configured execution backends (SIMULATION, PAPER, or LIVE)."""


class IMarketDataSynchronizer(abc.ABC):
    """Abstract contract for synchronizing market pricing with paper trading accounts."""

    @abc.abstractmethod
    def synchronize(self, symbol: str, price: float) -> None:
        """Process price updates, recalculating unrealized PnL, equity, and drawdowns."""
