"""Thread-safe repository caching trade journals and statistics with PostgreSQL delegation.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.trade_journal.interfaces import ITradeJournalRepository
from research_platform.trade_journal.models import TradeJournal, TradeStatistics, DailyJournal
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.trade_repository import PostgresTradeJournalRepository


class AwaitableStatsDict(dict):
    def __getattr__(self, name):
        if name == "winning_pct":
            return self.get("win_rate", 0.0)
        if name in self:
            return self[name]
        raise AttributeError(f"'AwaitableStatsDict' object has no attribute '{name}'")

    def __await__(self):
        async def _wrapper():
            return self
        return _wrapper().__await__()


class TradeJournalRepository(ITradeJournalRepository):
    """Memory-backed, thread-safe repository with PostgreSQL delegation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._journals: Dict[str, TradeJournal] = {}
        self._stats: Optional[TradeStatistics] = None
        self._daily_journals: Dict[str, DailyJournal] = {}

    def _get_pg_repo(self) -> Optional[PostgresTradeJournalRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresTradeJournalRepository(session_manager)
        return None

    def save_journal(self, journal: TradeJournal) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_journal(journal)
            
        with self._lock:
            self._journals[journal.journal_id] = journal

    def get_journal(self, journal_id: str) -> Optional[TradeJournal]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_journal(journal_id)
            
        with self._lock:
            return self._journals.get(journal_id)

    def list_journals(self) -> List[TradeJournal]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.list_journals()
            
        with self._lock:
            return list(self._journals.values())

    def save_statistics(self, stats: TradeStatistics) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_statistics(stats)
            
        with self._lock:
            self._stats = stats

    def get_latest_statistics(self) -> Optional[TradeStatistics]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_latest_statistics()
            
        with self._lock:
            return self._stats

    def get_statistics(self) -> AwaitableStatsDict:
        journals = self.list_journals()
        total_trades = len(journals)
        winning_trades = [j for j in journals if j.pnl > 0]
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
        total_pnl = sum(j.pnl for j in journals)
        
        gross_profits = sum(j.pnl for j in journals if j.pnl > 0)
        gross_losses = abs(sum(j.pnl for j in journals if j.pnl < 0))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else (gross_profits if gross_profits > 0 else 0.0)
        
        open_positions = 0
        try:
            container = ServiceRegistry().get_service("Container")
            if container:
                portfolio_store = container.resolve("PortfolioStateStore")
                if portfolio_store:
                    snap = portfolio_store.get_current_snapshot()
                    if snap:
                        open_positions = len(snap.positions)
        except Exception:
            pass
            
        return AwaitableStatsDict({
            "total_trades": total_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "profit_factor": profit_factor,
            "open_positions": open_positions
        })

    def save_daily_journal(self, journal: DailyJournal) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_daily_journal(journal)
            
        with self._lock:
            self._daily_journals[journal.date] = journal

    def get_daily_journal(self, date_str: str) -> Optional[DailyJournal]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_daily_journal(date_str)
            
        with self._lock:
            return self._daily_journals.get(date_str)
