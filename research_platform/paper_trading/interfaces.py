"""Abstract contracts for the Institutional Paper Trading Foundation.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional
from research_platform.paper_trading.models import (
    PaperAccount,
    PaperOrder,
    PaperPosition,
    TradeJournalEntry,
)


class IPaperBrokerAdapter(abc.ABC):
    """Abstract contract for executing paper trades against exchange sandbox."""

    @abc.abstractmethod
    def execute_order(self, account: PaperAccount, order: PaperOrder) -> PaperOrder:
        """Process paper order, calculate commission fees and return filled order."""


class IPaperExchange(abc.ABC):
    """Abstract contract for matching paper orders against pricing feeds."""

    @abc.abstractmethod
    def match_order(self, order: PaperOrder, price: float, spread: float) -> PaperOrder:
        """Match paper order details against target market pricing parameters."""


class IPaperTradingRepository(abc.ABC):
    """Abstract contract for persisting paper session parameters, logs, and orders."""

    @abc.abstractmethod
    def save_account(self, account: PaperAccount) -> None:
        """Persist paper account balance states."""

    @abc.abstractmethod
    def get_account(self, account_id: str) -> Optional[PaperAccount]:
        """Retrieve paper account status by ID."""

    @abc.abstractmethod
    def save_order(self, order: PaperOrder) -> None:
        """Persist a paper order state record."""

    @abc.abstractmethod
    def get_order(self, order_id: str) -> Optional[PaperOrder]:
        """Retrieve order details by ID."""

    @abc.abstractmethod
    def list_orders(self, status: Optional[str] = None) -> List[PaperOrder]:
        """List orders matching status checks."""

    @abc.abstractmethod
    def save_position(self, position: PaperPosition) -> None:
        """Persist open position properties."""

    @abc.abstractmethod
    def get_position(self, symbol: str) -> Optional[PaperPosition]:
        """Retrieve open position details by symbol."""

    @abc.abstractmethod
    def list_positions(self) -> List[PaperPosition]:
        """List all open position items."""

    @abc.abstractmethod
    def save_journal(self, entry: TradeJournalEntry) -> None:
        """Persist post-trade review journal entries."""

    @abc.abstractmethod
    def list_journals(self) -> List[TradeJournalEntry]:
        """List all logs journal entries."""


class IPaperTradingOrchestrator(abc.ABC):
    """Abstract contract for paper trading orchestrator systems."""
    pass
