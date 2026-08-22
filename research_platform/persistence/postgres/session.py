"""SQLAlchemy session manager and transaction scope controls.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import sessionmaker, Session

from research_platform.persistence.postgres.connection import DatabaseConnection


import threading

class DatabaseSessionManager:
    """Manages transactional Session instances with thread-local tracking."""

    def __init__(self, db_connection: Any) -> None:
        if hasattr(db_connection, "connection") and db_connection.connection is not None:
            self.connection = db_connection.connection
        else:
            self.connection = db_connection
        self._sessionmaker = sessionmaker(bind=self.connection.engine, expire_on_commit=False)
        self._local = threading.local()
    @property
    def active_session(self) -> Optional[Session]:
        return getattr(self._local, "active_session", None)

    def get_session(self) -> Session:
        if self.active_session is not None:
            return self.active_session
        return self._sessionmaker()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provides a transactional scope around a series of operations."""
        if getattr(self._local, "active_session", None) is not None:
            yield self._local.active_session
            return

        session = self.get_session()
        self._local.active_session = session
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            self._local.active_session = None
            session.close()
