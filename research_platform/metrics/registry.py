"""R55 Metrics Registry — central thread-safe metric store."""

from __future__ import annotations

import threading
import logging
from collections import defaultdict, deque
from typing import Dict, Deque, List, Optional

from research_platform.metrics.models import MetricPoint, MetricSeries

logger = logging.getLogger(__name__)
MAX_SERIES_POINTS = 500


class MetricsRegistry:
    """Thread-safe central registry for all MetricPoint series."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._series: Dict[str, Deque[MetricPoint]] = defaultdict(lambda: deque(maxlen=MAX_SERIES_POINTS))

    def record(self, point: MetricPoint) -> None:
        with self._lock:
            self._series[point.name].append(point)

    def record_value(self, name: str, value: float, **kwargs) -> MetricPoint:
        from research_platform.metrics.models import MetricType, MetricUnit
        point = MetricPoint(name=name, value=value, **kwargs)
        self.record(point)
        return point

    def get_series(self, name: str, limit: int = 100) -> MetricSeries:
        with self._lock:
            points = list(self._series.get(name, []))[-limit:]
        return MetricSeries(name=name, points=points)

    def get_latest(self, name: str) -> Optional[MetricPoint]:
        with self._lock:
            series = self._series.get(name)
            return series[-1] if series else None

    def list_metrics(self) -> List[str]:
        with self._lock:
            return list(self._series.keys())

    def total_count(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._series.values())

    def clear(self) -> None:
        with self._lock:
            self._series.clear()
