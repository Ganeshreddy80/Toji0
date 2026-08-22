"""Feed Heartbeat and Latency Monitor (Sprint 9B)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
from typing import Optional

from paper_trading.models.market_models import FeedStatus

logger = logging.getLogger(__name__)


class HeartbeatMonitor:
    """Thread-safe feed telemetry monitor tracking latency, heartbeat timestamps, and stale feed states."""

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self._lock = threading.RLock()
        self._timeout_seconds = timeout_seconds

        self._connected: bool = False
        self._last_heartbeat: datetime = datetime.now(timezone.utc)
        self._latency_ms: float = 0.0
        self._reconnect_count: int = 0

    def record_heartbeat(self, timestamp: Optional[datetime] = None, latency_ms: Optional[float] = None) -> FeedStatus:
        """Record feed activity tick/heartbeat and update latency metrics."""
        now = datetime.now(timezone.utc)
        ts = timestamp or now

        with self._lock:
            self._connected = True
            self._last_heartbeat = ts

            if latency_ms is not None:
                self._latency_ms = max(0.0, latency_ms)
            elif timestamp:
                diff_sec = (now - ts).total_seconds()
                self._latency_ms = max(0.0, diff_sec * 1000.0)

            return self.get_status()

    def set_connected(self, connected: bool) -> FeedStatus:
        """Set connection state."""
        with self._lock:
            self._connected = connected
            return self.get_status()

    def increment_reconnect_count(self) -> int:
        """Increment cumulative reconnect counter."""
        with self._lock:
            self._reconnect_count += 1
            return self._reconnect_count

    def is_stale(self, current_time: Optional[datetime] = None) -> bool:
        """Check if feed heartbeat has timed out beyond threshold."""
        now = current_time or datetime.now(timezone.utc)
        with self._lock:
            if not self._connected:
                return True
            elapsed = (now - self._last_heartbeat).total_seconds()
            return elapsed > self._timeout_seconds

    def get_status(self) -> FeedStatus:
        """Get current immutable FeedStatus telemetry snapshot."""
        with self._lock:
            return FeedStatus(
                connected=self._connected,
                latency_ms=self._latency_ms,
                heartbeat_time=self._last_heartbeat,
                reconnect_count=self._reconnect_count,
            )
