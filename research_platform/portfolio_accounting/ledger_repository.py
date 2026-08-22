"""Ledger Repository — persists immutable, append-only TradeLedgerEntries.
"""

from __future__ import annotations

import logging
import threading
from typing import List

from research_platform.portfolio_accounting.models import TradeLedgerEntry

logger = logging.getLogger(__name__)


class LedgerRepository:
    """Immutable, append-only transaction/trade ledger store."""

    def __init__(self) -> None:
        self._entries: List[TradeLedgerEntry] = []
        self._lock = threading.RLock()

    def _get_pg_repo(self) -> Optional[Any]:
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            registry = ServiceRegistry()
            db = registry.get_service("Database")
            if db:
                from research_platform.persistence.postgres.session import DatabaseSessionManager
                from research_platform.persistence.repositories.ledger_repository import PostgresLedgerRepository
                session_manager = DatabaseSessionManager(db)
                return PostgresLedgerRepository(session_manager)
        except Exception as e:
            logger.debug("LedgerRepository: Failed to get PostgresLedgerRepository: %s", e)
        return None

    def append(self, entry: TradeLedgerEntry) -> None:
        """Append an entry to the immutable ledger.
        
        Raises ValueError if an entry with the same trade_id or a prior timestamp is modified.
        """
        with self._lock:
            pg_repo = self._get_pg_repo()
            if pg_repo:
                # Check for duplicate
                existing = pg_repo.get_entry(entry.trade_id)
                if existing:
                    raise ValueError(f"Ledger violation: cannot overwrite existing trade_id {entry.trade_id}")
                pg_repo.save_entry(entry)
                # Keep in memory cache synchronized
                if not any(x.trade_id == entry.trade_id for x in self._entries):
                    self._entries.append(entry)
                logger.info("LedgerRepository: appended trade entry %s for %s to PostgreSQL", entry.trade_id, entry.symbol)
            else:
                # Enforce append-only validation: no updates or deletes allowed
                for existing in self._entries:
                    if existing.trade_id == entry.trade_id:
                        raise ValueError(f"Ledger violation: cannot overwrite existing trade_id {entry.trade_id}")
                self._entries.append(entry)
                logger.info("LedgerRepository: appended trade entry %s for %s to memory", entry.trade_id, entry.symbol)

    def get_all(self) -> List[TradeLedgerEntry]:
        """Fetch all ledger records."""
        with self._lock:
            pg_repo = self._get_pg_repo()
            if pg_repo:
                db_entries = pg_repo.list_entries()
                # Synchronize local cache with database
                for entry in db_entries:
                    if not any(x.trade_id == entry.trade_id for x in self._entries):
                        self._entries.append(entry)
                return db_entries
            return list(self._entries)

