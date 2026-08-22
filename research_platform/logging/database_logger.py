"""R52 Database Logger — records SQL query durations, connection events, and errors.
"""

from __future__ import annotations

import logging
from research_platform.logging.rotation import create_rotating_file_handler
from research_platform.logging.formatter import StructuredJsonFormatter

_db_logger = logging.getLogger("toji.database")
if not _db_logger.handlers:
    _h = create_rotating_file_handler("logs", "database.log", formatter=StructuredJsonFormatter())
    _db_logger.addHandler(_h)
    _db_logger.setLevel(logging.DEBUG)
    _db_logger.propagate = False


class DatabaseLogger:
    """Structured database operation log emitter."""

    def query(self, operation: str, table: str, duration_ms: float) -> None:
        _db_logger.debug(
            "DB_QUERY | op=%s | table=%s | duration_ms=%.3f", operation, table, duration_ms,
            extra={"correlation_id": table, "extra_data": {"op": operation, "duration_ms": duration_ms}}
        )

    def connection_error(self, host: str, error: str) -> None:
        _db_logger.error(
            "DB_CONN_ERROR | host=%s | error=%s", host, error,
            extra={"correlation_id": "DB_CONN", "extra_data": {"host": host, "error": error}}
        )

    def reconnected(self, host: str) -> None:
        _db_logger.info(
            "DB_RECONNECTED | host=%s", host,
            extra={"correlation_id": "DB_CONN", "extra_data": {"host": host}}
        )
