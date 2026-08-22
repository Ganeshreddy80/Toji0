"""Heartbeat Monitor tracking latency heartbeats.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from research_platform.live_trading.models import HeartbeatStatus

logger = logging.getLogger(__name__)


class HeartbeatMonitor:
    """Evaluates request latencies and triggers connection timeout alerts."""

    def __init__(self, timeout_limit_ms: float = 1000.0) -> None:
        self.timeout_limit_ms = timeout_limit_ms
        self._last_heartbeat: Optional[datetime] = None

    def record_pulse(self, latency_ms: float) -> HeartbeatStatus:
        """Update last pulse received timestamp and verify timeout checks."""
        self._last_heartbeat = datetime.now(timezone.utc)
        
        status = "ALIVE"
        if latency_ms > self.timeout_limit_ms:
            status = "TIMEOUT"
            logger.warning("Heartbeat Timeout Alert: latency is %f ms.", latency_ms)

        return HeartbeatStatus(
            heartbeat_id=str(uuid.uuid4()),
            status=status,
            latency_ms=latency_ms
        )
