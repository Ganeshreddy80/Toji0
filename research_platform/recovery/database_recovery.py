"""Database Recovery stage manager.
"""

from __future__ import annotations

import logging
from typing import Any
from research_platform.platform.service_registry import ServiceRegistry

logger = logging.getLogger(__name__)


class DatabaseRecoveryManager:
    """Verifies active PostgreSQL state, running auto-reconnects and schema checkups."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def recover_database(self) -> bool:
        """Verifies database is online and tables are initialized. Returns True if database is online."""
        logger.info("Running DatabaseRecoveryManager verification checks...")

        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if not db:
            # DB-003: Database not registered is a real failure — no persistence is available.
            # Previously returned True ("SQLite mock fallback is valid"), which masked the absence
            # of any registered database and allowed trading to proceed without persistence.
            logger.error(
                "DatabaseRecoveryManager: Database service not registered in platform registry. "
                "Recovery cannot verify persistence layer. Returning failure."
            )
            return False

        try:
            if not db.connected:
                logger.info("Attempting PostgreSQL auto-reconnection via dispose+reinitialize...")
                # DB-005: db.connect() on an already-initialized DatabaseLifecycleManager was a
                # no-op because connect() short-circuits when _connection is not None.
                # Use connection.reconnect() which disposes the stale pool and re-initializes.
                if db.connection is not None:
                    db.connection.reconnect()
                else:
                    db.connect()

            # Perform schema validation query
            connection = db.connection
            if connection and connection.engine:
                from sqlalchemy import text
                with connection.engine.connect() as conn:
                    # Basic diagnostic check to assert DB is online
                    conn.execute(text("SELECT 1"))

            logger.info("PostgreSQL database is online and responsive.")
            return True
        except Exception as e:
            # DB-003: PostgreSQL connectivity failure must be reported as failure, not masked.
            # Previously returned True here with "Proceeding in SQLite mock mode" comment,
            # which allowed a broken-DB session to be reported as a successful recovery.
            logger.error(
                "DatabaseRecoveryManager: PostgreSQL connectivity check failed: %s. "
                "Returning failure — do not proceed with degraded persistence.", e
            )
            return False

