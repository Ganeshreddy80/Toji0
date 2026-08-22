"""Database repository saving logs, metrics points, and active alerts.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.observability.interfaces import IObservabilityRepository
from research_platform.observability.models import Alert, LogEntry, MetricPoint, Span


class ObservabilityRepository(IObservabilityRepository):
    """Memory database repository for observability metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._logs: List[LogEntry] = []
        self._metrics: List[MetricPoint] = []
        self._spans: Dict[str, Span] = {}
        self._alerts: Dict[str, Alert] = {}

    def save_log(self, entry: LogEntry) -> None:
        with self._lock:
            self._logs.append(entry)

    def save_metric(self, point: MetricPoint) -> None:
        with self._lock:
            self._metrics.append(point)

    def save_span(self, span: Span) -> None:
        with self._lock:
            self._spans[span.span_id] = span

    def save_alert(self, alert: Alert) -> None:
        with self._lock:
            self._alerts[alert.alert_id] = alert

    def list_logs(self) -> List[LogEntry]:
        with self._lock:
            return list(self._logs)

    def list_metrics(self) -> List[MetricPoint]:
        with self._lock:
            return list(self._metrics)

    def list_spans(self) -> List[Span]:
        with self._lock:
            return list(self._spans.values())

    def list_alerts(self) -> List[Alert]:
        with self._lock:
            return list(self._alerts.values())
