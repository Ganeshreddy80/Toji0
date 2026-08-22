"""Metrics Engine aggregating counters, gauges, and timers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from research_platform.observability.interfaces import IMetricsEngine
from research_platform.observability.models import MetricPoint


class MetricsEngine(IMetricsEngine):
    """Enforces increments and updates, holding rolling cache snapshots."""

    def __init__(self) -> None:
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}

    def record_metric(
        self,
        name: str,
        value: float,
        tags: Dict[str, str] = None
    ) -> MetricPoint:
        """Construct MetricPoint and track rolling count aggregates."""
        # Simple hist tracker
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)

        return MetricPoint(
            metric_name=name,
            value=value,
            tags=tags or {}
        )

    def increment_counter(self, name: str, amount: float = 1.0) -> None:
        self._counters[name] = self._counters.get(name, 0.0) + amount

    def update_gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def get_counter(self, name: str) -> float:
        return self._counters.get(name, 0.0)

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    def get_histogram_values(self, name: str) -> List[float]:
        return self._histograms.get(name, [])
