"""Structured logger and JSON formatter implementation.

``StructuredLogger`` wraps Python's standard ``logging`` module,
injecting structured context into every log record.

``JsonFormatter`` outputs log records as single-line JSON objects,
suitable for log aggregation pipelines.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from toji_platform.core.logging.interfaces import IStructuredLogger


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON.

    Output fields: ``timestamp``, ``level``, ``logger``,
    ``message``, and any extra ``context`` keys.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge structured context injected by StructuredLogger
        context: dict[str, Any] = getattr(record, "context", {})
        if context:
            log_entry["context"] = context

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class StructuredLogger(IStructuredLogger):
    """Per-module structured logger backed by stdlib logging.

    Args:
        name: Logger name (usually ``__name__`` of the calling module).
        level: Minimum log level (default ``INFO``).
        json_output: If ``True``, attach ``JsonFormatter`` to a
            ``StreamHandler`` on ``sys.stderr``.
    """

    def __init__(
        self,
        name: str,
        level: int = logging.INFO,
        json_output: bool = False,
    ) -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)

        if json_output and not self._logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(JsonFormatter())
            self._logger.addHandler(handler)

    # ── IStructuredLogger ──────────────────────────────────────────────

    def debug(self, message: str, **context: Any) -> None:
        self._log(logging.DEBUG, message, context)

    def info(self, message: str, **context: Any) -> None:
        self._log(logging.INFO, message, context)

    def warning(self, message: str, **context: Any) -> None:
        self._log(logging.WARNING, message, context)

    def error(self, message: str, **context: Any) -> None:
        self._log(logging.ERROR, message, context)

    def critical(self, message: str, **context: Any) -> None:
        self._log(logging.CRITICAL, message, context)

    # ── Internals ──────────────────────────────────────────────────────

    def _log(
        self,
        level: int,
        message: str,
        context: dict[str, Any],
    ) -> None:
        if context:
            self._logger.log(
                level,
                message,
                extra={"context": context},
            )
        else:
            self._logger.log(level, message)


def get_logger(
    name: str,
    level: int = logging.INFO,
    json_output: bool = False,
) -> StructuredLogger:
    """Convenience factory for obtaining a ``StructuredLogger``."""
    return StructuredLogger(name, level=level, json_output=json_output)
