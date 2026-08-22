"""Abstract contracts for the Observability Platform.
"""

from __future__ import annotations

import abc
from typing import Dict, List, Optional

from research_platform.observability.models import (
    Alert,
    HealthReport,
    LogEntry,
    MetricPoint,
    Span,
    Trace
)


class IStructuredLogger(abc.ABC):
    """Abstract contract for structured JSON logging."""

    @abc.abstractmethod
    def log(self, level: str, subsystem: str, message: str) -> LogEntry:
        """Construct and publish structured LogEntry."""


class IMetricsEngine(abc.ABC):
    """Abstract contract for operational metrics aggregation."""

    @abc.abstractmethod
    def record_metric(self, name: str, value: float) -> MetricPoint:
        """Construct and save MetricPoint."""


class ITracingEngine(abc.ABC):
    """Abstract contract for distributed tracing spans."""

    @abc.abstractmethod
    def start_span(self, name: str, parent_id: Optional[str] = None) -> Span:
        """Construct and save start of execution span."""


class IObservabilityRepository(abc.ABC):
    """Abstract database repository contract for observability logs."""

    @abc.abstractmethod
    def save_log(self, entry: LogEntry) -> None:
        """Persist a LogEntry."""

    @abc.abstractmethod
    def save_metric(self, point: MetricPoint) -> None:
        """Persist a MetricPoint."""

    @abc.abstractmethod
    def save_span(self, span: Span) -> None:
        """Persist a Span."""

    @abc.abstractmethod
    def save_alert(self, alert: Alert) -> None:
        """Persist an Alert."""
class IObservabilityOrchestrator(abc.ABC):
    """Abstract contract for observability orchestrator."""
    pass
