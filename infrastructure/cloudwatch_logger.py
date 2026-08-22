"""Thread-safe CloudWatch Logger Abstraction with Structured Batching (Sprint 12A)."""

from __future__ import annotations

import collections
import logging
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """CloudWatch log severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class CloudWatchLogEvent(BaseModel):
    """Immutable structured CloudWatch log event model."""

    log_group: str = Field(..., description="Target CloudWatch Log Group.")
    log_stream: str = Field(..., description="Target CloudWatch Log Stream.")
    level: LogLevel = Field(default=LogLevel.INFO, description="Log severity level.")
    message: str = Field(..., description="Log message string.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    extra: Dict[str, Any] = Field(default_factory=dict, description="Structured contextual metadata.")
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class CloudWatchLogger:
    """Thread-safe CloudWatch Logger maintaining a bounded in-memory log event queue with batch flushing."""

    def __init__(
        self,
        default_log_group: str = "/toji/platform/advisory",
        default_log_stream: str = "app-stream",
        max_queue_size: int = 1000,
    ) -> None:
        self._lock = threading.RLock()
        self._default_group = default_log_group
        self._default_stream = default_log_stream
        self._max_queue_size = max_queue_size
        # Bounded queue of CloudWatchLogEvent
        self._queue: collections.deque = collections.deque(maxlen=self._max_queue_size)
        self._flushed_history: List[CloudWatchLogEvent] = []

    def log(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        log_group: Optional[str] = None,
        log_stream: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> CloudWatchLogEvent:
        """Enqueue a structured log event."""
        with self._lock:
            event = CloudWatchLogEvent(
                log_group=log_group or self._default_group,
                log_stream=log_stream or self._default_stream,
                level=level,
                message=message,
                extra=extra or {},
            )
            self._queue.append(event)
            logger.debug("Enqueued CloudWatch log event: [%s] %s", level.value, message)
            return event

    def flush_batch(self, batch_size: int = 100) -> List[CloudWatchLogEvent]:
        """Flush up to batch_size log events from queue."""
        with self._lock:
            batch: List[CloudWatchLogEvent] = []
            count = min(batch_size, len(self._queue))
            for _ in range(count):
                batch.append(self._queue.popleft())
            self._flushed_history.extend(batch)
            logger.info("Flushed %d log events to CloudWatch batch", len(batch))
            return batch

    def queue_size(self) -> int:
        """Return count of currently queued log events."""
        with self._lock:
            return len(self._queue)

    def flushed_count(self) -> int:
        """Return total count of flushed log events."""
        with self._lock:
            return len(self._flushed_history)

    def clear(self) -> None:
        """Clear queued and flushed log events."""
        with self._lock:
            self._queue.clear()
            self._flushed_history.clear()
