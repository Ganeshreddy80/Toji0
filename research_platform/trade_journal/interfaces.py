"""Abstract contracts for the Institutional Trade Journal & Performance Analytics.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional
from research_platform.trade_journal.models import (
    TradeJournal,
    TradeReview,
    TradeStatistics,
    DailyJournal,
)


class ITradeJournalRepository(abc.ABC):
    """Abstract contract for persisting trade journals, reviews, and statistics."""

    @abc.abstractmethod
    def save_journal(self, journal: TradeJournal) -> None:
        """Persist a completed trade journal entry."""

    @abc.abstractmethod
    def get_journal(self, journal_id: str) -> Optional[TradeJournal]:
        """Retrieve journal entry details by ID."""

    @abc.abstractmethod
    def list_journals(self) -> List[TradeJournal]:
        """List all recorded journals."""

    @abc.abstractmethod
    def save_statistics(self, stats: TradeStatistics) -> None:
        """Persist recalculated statistics aggregates."""

    @abc.abstractmethod
    def get_latest_statistics(self) -> Optional[TradeStatistics]:
        """Retrieve the latest portfolio statistics metrics."""

    @abc.abstractmethod
    def get_statistics(self) -> Any:
        """Get compiled trade statistics dictionary/object."""

    @abc.abstractmethod
    def save_daily_journal(self, journal: DailyJournal) -> None:
        """Persist compiled daily journal snapshot."""

    @abc.abstractmethod
    def get_daily_journal(self, date_str: str) -> Optional[DailyJournal]:
        """Retrieve compiled daily journal snapshot by date."""


class ITradeJournal(abc.ABC):
    """Abstract contract for trade journal entry compilation."""

    @abc.abstractmethod
    def record_completed_trade(self, order_id: str) -> TradeJournal:
        """Retrieve execution metrics, compile MFE/MAE, run AI review, and write journal."""


class ITradeReviewer(abc.ABC):
    """Abstract contract for AI reviews processing."""

    @abc.abstractmethod
    def generate_review(self, journal: TradeJournal) -> TradeReview:
        """Interfaces with AIIntelligenceOrchestrator to produce mistakes logs."""


class ITradeStatistics(abc.ABC):
    """Abstract contract for compiling portfolio-wide performance summaries."""

    @abc.abstractmethod
    def calculate_statistics(self, journals: List[TradeJournal]) -> TradeStatistics:
        """Compute expectation, Sharpe, Sortino ratios, profit factors, and streaks."""
