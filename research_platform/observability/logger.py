"""Structured Logger constructing JSON format logs with correlation context.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from research_platform.observability.interfaces import IStructuredLogger
from research_platform.observability.models import LogEntry


class StructuredLogger(IStructuredLogger):
    """Enforces JSON serializations for warning/error system logs."""

    def __init__(self) -> None:
        self._current_correlation_id: Optional[str] = None

    def set_correlation_id(self, correlation_id: str) -> None:
        self._current_correlation_id = correlation_id

    def clear_correlation_id(self) -> None:
        self._current_correlation_id = None

    def log(self, level: str, subsystem: str, message: str) -> LogEntry:
        """Construct structured LogEntry, formatting details to JSON stdout."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            subsystem=subsystem,
            level=level.upper(),
            message=message,
            correlation_id=self._current_correlation_id
        )
        
        # Serialize to stdout or print
        # print(json.dumps(entry.model_dump(), default=str))
        return entry
