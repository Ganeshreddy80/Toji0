"""Abstract contracts for the Portfolio Governor subsystem."""

from __future__ import annotations

import abc
from typing import Any


class IPortfolioGovernor(abc.ABC):
    """Abstract contract for pre-execution signal governance."""

    @abc.abstractmethod
    def evaluate(self, signal: Any) -> Any:
        """Evaluate an incoming trade signal and return a PortfolioDecision.

        Args:
            signal: ActiveSignal (or any object with .symbol, .direction, .signal_id attrs)

        Returns:
            PortfolioDecision with approved flag and rejection reason.
        """

    @abc.abstractmethod
    def record_fill(self, symbol: str, direction: str, quantity: float, price: float) -> None:
        """Update governor state after a confirmed order fill.

        Must be called after TradeManager reports a successful FILLED status.
        """

    @abc.abstractmethod
    def get_portfolio_summary(self) -> dict:
        """Return a serialisable summary of open positions and blocked trade counts."""
