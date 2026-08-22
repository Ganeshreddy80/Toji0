"""Transaction manager orchestrating atomic transactions.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session

from research_platform.persistence.postgres.session import DatabaseSessionManager


class TransactionManager:
    """Coordinates commit and rollback sequences across repositories."""

    def __init__(self, session_manager: DatabaseSessionManager) -> None:
        self.session_manager = session_manager

    @contextmanager
    def transaction(self) -> Generator[Session, None, None]:
        with self.session_manager.session_scope() as session:
            yield session
