"""R52 Logging repository — persists audit and trade records to PostgreSQL.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from typing import Deque, Dict, Any

logger = logging.getLogger(__name__)

MAX_IN_MEMORY = 10_000


class LogRepository:
    """Thread-safe in-memory log buffer with PostgreSQL delegation fallback."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._audit_buffer: Deque[Dict[str, Any]] = deque(maxlen=MAX_IN_MEMORY)
        self._trade_buffer: Deque[Dict[str, Any]] = deque(maxlen=MAX_IN_MEMORY)

    def save_audit(self, record: Dict[str, Any]) -> None:
        with self._lock:
            self._audit_buffer.append(record)
        self._try_persist("audit_logs", record)

    def save_trade(self, record: Dict[str, Any]) -> None:
        with self._lock:
            self._trade_buffer.append(record)
        self._try_persist("trade_logs", record)

    def _try_persist(self, key: str, record: Dict[str, Any]) -> None:
        """Best-effort PostgreSQL config entry save."""
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            from research_platform.persistence.repositories.configuration_repository import PostgresConfigurationRepository
            from research_platform.configuration.models import ConfigurationEntry
            registry = ServiceRegistry()
            db = registry.get_service("Database")
            if db:
                from research_platform.persistence.postgres.session import DatabaseSessionManager
                sm = DatabaseSessionManager(db)
                repo = PostgresConfigurationRepository(sm)
                repo.save_config(ConfigurationEntry(key=f"{key}:{record.get('timestamp','')}", value=record))
        except Exception as e:
            logger.debug("Log persistence skipped: %s", e)

    def get_recent_audit(self, n: int = 100) -> list:
        with self._lock:
            return list(self._audit_buffer)[-n:]

    def get_recent_trades(self, n: int = 100) -> list:
        with self._lock:
            return list(self._trade_buffer)[-n:]
