"""Thread-safe Bounded Metrics Repository with Aggregation & Rolling Averages (Sprint 12C)."""

from __future__ import annotations

import collections
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict

from operations.metrics_collector import MetricSnapshot

logger = logging.getLogger(__name__)


class MetricAggregate(BaseModel):
    """Immutable aggregate statistical model for a metric series."""

    metric_name: str
    count: int
    min_value: float
    max_value: float
    mean_value: float
    latest_value: float
    is_advisory_only: bool = True

    model_config = ConfigDict(frozen=True)


class MetricsRepository:
    """Thread-safe in-memory Bounded Metrics Repository providing queries and aggregations."""

    def __init__(self, max_metrics: int = 10000) -> None:
        self._lock = threading.RLock()
        self._max_metrics = max_metrics
        # Bounded deque storing MetricSnapshot instances
        self._metrics: collections.deque = collections.deque(maxlen=self._max_metrics)

    def add_snapshot(self, snapshot: MetricSnapshot) -> None:
        """Add a single metric snapshot to the repository."""
        with self._lock:
            self._metrics.append(snapshot)

    def add_snapshots(self, snapshots: List[MetricSnapshot]) -> None:
        """Add a batch of metric snapshots to the repository."""
        with self._lock:
            for s in snapshots:
                self._metrics.append(s)

    def get_snapshots(
        self,
        metric_name: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[MetricSnapshot]:
        """Query and filter stored snapshots by metric name, labels, and time bounds."""
        with self._lock:
            results: List[MetricSnapshot] = []
            for s in self._metrics:
                if metric_name and s.metric_name != metric_name:
                    continue
                if start_time and s.timestamp < start_time:
                    continue
                if end_time and s.timestamp > end_time:
                    continue
                if labels:
                    match = all(s.labels.get(k) == v for k, v in labels.items())
                    if not match:
                        continue
                results.append(s)
            return results

    def aggregate_metric(
        self,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Optional[MetricAggregate]:
        """Compute min, max, mean, count, and latest values for a metric."""
        with self._lock:
            matches = self.get_snapshots(metric_name=metric_name, start_time=start_time, end_time=end_time)
            if not matches:
                return None

            values = [m.value for m in matches]
            return MetricAggregate(
                metric_name=metric_name,
                count=len(values),
                min_value=min(values),
                max_value=max(values),
                mean_value=sum(values) / len(values),
                latest_value=values[-1],
            )

    def calculate_rolling_average(
        self,
        metric_name: str,
        window_seconds: float = 300.0,
    ) -> float:
        """Calculate rolling average over the specified trailing time window in seconds."""
        with self._lock:
            now = datetime.now(timezone.utc)
            cutoff = datetime.fromtimestamp(now.timestamp() - window_seconds, tz=timezone.utc)
            matches = self.get_snapshots(metric_name=metric_name, start_time=cutoff)
            if not matches:
                return 0.0
            return sum(m.value for m in matches) / len(matches)

    def time_window_query(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> List[MetricSnapshot]:
        """Query all metric snapshots within a time window."""
        return self.get_snapshots(start_time=start_time, end_time=end_time)

    def count(self) -> int:
        """Return total count of stored metric snapshots."""
        with self._lock:
            return len(self._metrics)

    def clear(self) -> None:
        """Clear all stored metric snapshots."""
        with self._lock:
            self._metrics.clear()
