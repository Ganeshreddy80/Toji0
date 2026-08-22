"""Database repository saving strategies reviews, journal logs, and recommendations.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.ai_intelligence.models import (
    DailyReport,
    JournalEntry,
    Recommendation,
    StrategyReview,
    TradeReview
)


class AIIntelligenceRepository:
    """Memory database repository for AI decisions reviews."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._strategy_reviews: Dict[str, StrategyReview] = {}
        self._trade_reviews: Dict[str, TradeReview] = {}
        self._recommendations: Dict[str, Recommendation] = {}
        self._daily_reports: Dict[str, DailyReport] = {}
        self._journals: Dict[str, JournalEntry] = {}

    def save_strategy_review(self, review: StrategyReview) -> None:
        with self._lock:
            self._strategy_reviews[review.strategy_id] = review

    def get_strategy_review(self, strategy_id: str) -> Optional[StrategyReview]:
        with self._lock:
            return self._strategy_reviews.get(strategy_id)

    def save_trade_review(self, review: TradeReview) -> None:
        with self._lock:
            self._trade_reviews[review.trade_id] = review

    def get_trade_review(self, trade_id: str) -> Optional[TradeReview]:
        with self._lock:
            return self._trade_reviews.get(trade_id)

    def save_recommendation(self, rec: Recommendation) -> None:
        with self._lock:
            self._recommendations[rec.recommendation_id] = rec

    def list_recommendations(self) -> List[Recommendation]:
        with self._lock:
            return list(self._recommendations.values())

    def save_daily_report(self, report: DailyReport) -> None:
        with self._lock:
            self._daily_reports[report.report_id] = report

    def save_journal_entry(self, entry: JournalEntry) -> None:
        with self._lock:
            self._journals[entry.entry_id] = entry

    def list_journal_entries(self) -> List[JournalEntry]:
        with self._lock:
            return list(self._journals.values())
