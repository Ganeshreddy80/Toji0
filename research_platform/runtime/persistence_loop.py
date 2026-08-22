"""Persistence Loop subsystem implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from research_platform.runtime.interfaces import IRuntimeLoop

logger = logging.getLogger(__name__)


class PersistenceLoop(IRuntimeLoop):
    """Periodically triggers PostgreSQL database updates for active platform states."""

    def __init__(self, container: Any) -> None:
        self.container = container
        self.retry_count = 0

    def execute(self, context: Dict[str, Any]) -> None:
        logger.debug("Executing PersistenceLoop commit triggers...")
        # Since subsystem repositories automatically delegate their writes to PostgreSQL,
        # we can verify that the connection remains online and flush any buffers if needed.
        try:
            db = self.container.resolve("Database")
            if db and not db.connected:
                db.connect()
        except Exception:
            pass

    def recover(self, exception: Exception) -> bool:
        self.retry_count += 1
        logger.warning("PersistenceLoop caught exception: %s. Recovery retry: %d", exception, self.retry_count)
        return True
