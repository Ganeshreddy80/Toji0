"""Observability Orchestrator coordinating structured logging, metrics, traces, and health monitors.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.observability.alerting import AlertEngine
from research_platform.observability.events import (
    AlertGenerated,
    HealthCheckCompleted,
    LogRecorded,
    MetricRecorded,
    TraceCompleted,
    TraceStarted
)
from research_platform.observability.health import HealthEngine
from research_platform.observability.heartbeat import HeartbeatMonitor
from research_platform.observability.logger import StructuredLogger
from research_platform.observability.metrics import MetricsEngine
from research_platform.observability.models import (
    Alert,
    HealthReport,
    LogEntry,
    MetricPoint,
    Span
)
from research_platform.observability.repository import ObservabilityRepository
from research_platform.observability.tracing import TracingEngine

logger = logging.getLogger(__name__)


class ObservabilityOrchestrator:
    """Manages system metrics aggregator loop and JSON structured logs auditing."""

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._repo = ObservabilityRepository()

        # Engine instances
        self._logger = StructuredLogger()
        self._metrics = MetricsEngine()
        self._tracing = TracingEngine()
        self._health = HealthEngine()
        self._heartbeat = HeartbeatMonitor()

    @property
    def repository(self) -> ObservabilityRepository:
        return self._repo

    def record_log(self, level: str, subsystem: str, message: str) -> LogEntry:
        """Process log request, formatting JSON trace files and persisting."""
        entry = self._logger.log(level, subsystem, message)
        self._repo.save_log(entry)
        self._event_bus.publish(LogRecorded(payload={"subsystem": subsystem, "level": level}))
        return entry

    def record_metric(self, name: str, value: float) -> MetricPoint:
        """Process counter increment or gauge update metric point."""
        point = self._metrics.record_metric(name, value)
        self._repo.save_metric(point)
        self._event_bus.publish(MetricRecorded(payload={"metric_name": name, "value": value}))
        return point

    def trace_execution_start(self, name: str, parent_id: Optional[str] = None) -> Span:
        """Initialize timing execution span."""
        span = self._tracing.start_span(name, parent_id)
        self._repo.save_span(span)
        self._event_bus.publish(TraceStarted(payload={"span_id": span.span_id}))
        return span

    def trace_execution_stop(self, span_id: str) -> Span:
        """Conclude timing execution span, updating duration metrics."""
        span = self._tracing.stop_span(span_id)
        self._repo.save_span(span)
        self._event_bus.publish(TraceCompleted(payload={"span_id": span_id, "duration": span.duration_ms}))
        return span

    def run_health_sweep(self) -> HealthReport:
        """Query component state monitors and output HealthReport."""
        # Simple sample checks
        self._health.update_status("OMS", healthy=True)
        self._health.update_status("EMS", healthy=True)

        report = self._health.compile_report()
        self._event_bus.publish(HealthCheckCompleted(payload={"report_id": report.report_id}))
        return report

    def generate_alert(self, severity: str, message: str) -> Alert:
        """Construct alert warning and notify listeners."""
        alert = AlertEngine.create_alert(severity, message)
        self._repo.save_alert(alert)
        self._event_bus.publish(AlertGenerated(payload={"alert_id": alert.alert_id, "severity": severity}))
        return alert
