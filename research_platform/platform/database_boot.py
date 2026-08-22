"""Database lifecycle manager executing schema migrations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from research_platform.persistence.postgres.connection import DatabaseConnection
from research_platform.persistence.postgres.migrations import run_migrations

logger = logging.getLogger(__name__)


class DatabaseLifecycleManager:
    """Manages database connection and dynamic migrations lifecycle."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.connected = False
        self._connection: DatabaseConnection | None = None

    def connect(self) -> Any:
        """Initialize database engine and build schema."""
        if self._connection is None:
            self._connection = DatabaseConnection(self.config)
            self._connection.initialize()
            
            # Automatically run schema migrations on the active engine (Postgres or SQLite fallback)
            run_migrations(self._connection.engine)
            self.connected = True
            logger.info("Database lifecycle connection initialized successfully.")
        return self._connection.connect()

    def disconnect(self) -> None:
        """Close connection pool and release resources."""
        if self._connection and self._connection.engine:
            self._connection.engine.dispose()
        self.connected = False
        logger.info("Database connection pool safely released.")

    def get_session(self) -> Any:
        """Helper to get a database session."""
        if not self._connection:
            self.connect()
        from research_platform.persistence.postgres.session import DatabaseSessionManager
        return DatabaseSessionManager(self._connection).get_session()

    @property
    def connection(self) -> DatabaseConnection | None:
        return self._connection
