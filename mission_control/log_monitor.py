"""Thread-safe Log Monitor & Log Event Classifier for Mission Control (Sprint 10B)."""

from __future__ import annotations

import collections
from datetime import datetime, timezone
from enum import Enum
import logging
import threading
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """Log severity level enumeration."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogEntry(BaseModel):
    """Immutable structured log entry model."""

    level: LogLevel = Field(..., description="Log severity level.")
    message: str = Field(..., description="Log message text.")
    service_name: str = Field(default="system", description="Originating service name.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Log entry timestamp.",
    )
    details: Optional[Dict[str, str]] = Field(default=None, description="Structured log attributes.")

    model_config = ConfigDict(frozen=True)


class LogMonitor:
    """Thread-safe Log Monitor recording, filtering, and aggregating operational log events."""

    def __init__(self, max_history: int = 1000) -> None:
        self._lock = threading.RLock()
        self._logs: collections.deque[LogEntry] = collections.deque(maxlen=max_history)
        self._counts: Dict[LogLevel, int] = {level: 0 for level in LogLevel}

    def record_log(
        self,
        level: LogLevel,
        message: str,
        service_name: str = "system",
        details: Optional[Dict[str, str]] = None,
    ) -> LogEntry:
        """Record a structured log entry."""
        with self._lock:
            entry = LogEntry(
                level=level,
                message=message,
                service_name=service_name,
                timestamp=datetime.now(timezone.utc),
                details=details,
            )
            self._logs.append(entry)
            self._counts[level] += 1
            return entry

    def record_info(self, message: str, service_name: str = "system") -> LogEntry:
        """Record an INFO level log entry."""
        return self.record_log(LogLevel.INFO, message, service_name)

    def record_warning(self, message: str, service_name: str = "system") -> LogEntry:
        """Record a WARNING level log entry."""
        return self.record_log(LogLevel.WARNING, message, service_name)

    def record_error(self, message: str, service_name: str = "system") -> LogEntry:
        """Record an ERROR level log entry."""
        return self.record_log(LogLevel.ERROR, message, service_name)

    def record_critical(self, message: str, service_name: str = "system") -> LogEntry:
        """Record a CRITICAL level log entry."""
        return self.record_log(LogLevel.CRITICAL, message, service_name)

    def filter_logs(
        self,
        level: Optional[LogLevel] = None,
        service_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[LogEntry]:
        """Filter stored log entries by severity level and/or service name."""
        with self._lock:
            filtered: List[LogEntry] = []
            for entry in self._logs:
                if level and entry.level != level:
                    continue
                if service_name and entry.service_name != service_name:
                    continue
                filtered.append(entry)

            return filtered[-limit:] if limit else filtered

    def get_log_counts(self) -> Dict[str, int]:
        """Get aggregate total log counts per severity level."""
        with self._lock:
            return {level.value: count for level, count in self._counts.items()}

    def get_recent_logs(self, limit: int = 50) -> List[LogEntry]:
        """Get list of most recent log entries up to limit."""
        with self._lock:
            return list(self._logs)[-limit:]

    def clear(self) -> None:
        """Clear recorded log history and reset level counts."""
        with self._lock:
            self._logs.clear()
            for level in LogLevel:
                self._counts[level] = 0
