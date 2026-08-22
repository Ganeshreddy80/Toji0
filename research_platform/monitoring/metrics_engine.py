"""Metrics engine accumulating telemetry values.
"""

from __future__ import annotations

from research_platform.monitoring.models import MetricCounter


class MetricsEngine:
    """Tracks increments for performance metric statistics."""

    def increment_metric(self, current: int, increment: int = 1) -> int:
        return current + increment
