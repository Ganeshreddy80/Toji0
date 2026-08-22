"""Health Monitor tracking latency metrics and connection status alerts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from research_platform.execution_engine.models import HealthMetric


class HealthMonitor:
    """Evaluates request latencies and triggers connection alerts."""

    def __init__(self, latency_threshold_ms: float = 500.0) -> None:
        self.latency_threshold_ms = latency_threshold_ms
        self._reconnects = 0
        self._successes = 0
        self._failures = 0

    def record_request(self, latency_ms: float, success: bool) -> HealthMetric:
        """Log next execution latency and compute success ratios."""
        if success:
            self._successes += 1
        else:
            self._failures += 1

        total = self._successes + self._failures
        success_ratio = float(self._successes / total) if total > 0 else 1.0

        return HealthMetric(
            metric_id=str(uuid.uuid4()),
            latency_ms=latency_ms,
            uptime_pct=100.0,
            success_ratio=success_ratio,
            reconnect_count=self._reconnects,
            timestamp=datetime.now(timezone.utc)
        )

    def record_reconnect(self) -> None:
        self._reconnects += 1
