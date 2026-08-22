"""Thread-safe paper trading repository with PostgreSQL delegation capabilities.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.paper_trading.interfaces import IPaperTradingRepository
from research_platform.paper_trading.models import PaperAccount, PaperOrder, PaperPosition, TradeJournalEntry
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.position_repository import PostgresPositionRepository


class PaperTradingRepository(IPaperTradingRepository):
    """Memory-backed, thread-safe repository with PostgreSQL delegation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._accounts: Dict[str, PaperAccount] = {}
        self._orders: Dict[str, PaperOrder] = {}
        self._positions: Dict[str, PaperPosition] = {}
        self._journals: List[TradeJournalEntry] = []

    def _get_pg_repo(self) -> Optional[PostgresPositionRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresPositionRepository(session_manager)
        return None

    def save_account(self, account: PaperAccount) -> None:
        with self._lock:
            self._accounts[account.account_id] = account

    def get_account(self, account_id: str) -> Optional[PaperAccount]:
        with self._lock:
            return self._accounts.get(account_id)

    def save_order(self, order: PaperOrder) -> None:
        with self._lock:
            self._orders[order.order_id] = order

    def get_order(self, order_id: str) -> Optional[PaperOrder]:
        with self._lock:
            return self._orders.get(order_id)

    def list_orders(self, status: Optional[str] = None) -> List[PaperOrder]:
        with self._lock:
            vals = list(self._orders.values())
            if status:
                return [o for o in vals if o.status == status]
            return vals

    def save_position(self, position: PaperPosition) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_position(position)
            
        with self._lock:
            self._positions[position.symbol] = position

    def get_position(self, symbol: str) -> Optional[PaperPosition]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_position(symbol)
            
        with self._lock:
            return self._positions.get(symbol)

    def list_positions(self) -> List[PaperPosition]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.list_positions()
            
        with self._lock:
            return list(self._positions.values())

    def save_journal(self, entry: TradeJournalEntry) -> None:
        with self._lock:
            self._journals.append(entry)

    def list_journals(self) -> List[TradeJournalEntry]:
        with self._lock:
            return list(self._journals)
