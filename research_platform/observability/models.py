"""Immutable Pydantic models for the Observability Platform.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LogEntry(BaseModel):
    """Structured JSON logging record wrapper."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    subsystem: str
    level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message: str
    correlation_id: Optional[str] = None
    thread_name: str = "main"

    model_config = ConfigDict(frozen=True)


class MetricPoint(BaseModel):
    """Single metrics record point."""

    metric_name: str
    value: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class CounterMetric(BaseModel):
    """Metrics counter wrapper."""

    metric_name: str
    count: float

    model_config = ConfigDict(frozen=True)


class GaugeMetric(BaseModel):
    """Metrics gauge wrapper."""

    metric_name: str
    value: float

    model_config = ConfigDict(frozen=True)


class HistogramMetric(BaseModel):
    """Metrics histogram counts distribution."""

    metric_name: str
    values: List[float] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class Span(BaseModel):
    """Execution timings span."""

    span_id: str
    trace_id: str
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    parent_span_id: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class Trace(BaseModel):
    """Distributed tracing collection."""

    trace_id: str
    spans: List[Span] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class HealthStatus(BaseModel):
    """Component status wrapper."""

    component_name: str
    healthy: bool
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class HealthReport(BaseModel):
    """Aggregated operational status report."""

    report_id: str
    statuses: List[HealthStatus] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class Alert(BaseModel):
    """Observability alert notice."""

    alert_id: str
    severity: str  # INFO, WARNING, ERROR, CRITICAL
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class AlertSeverity(BaseModel):
    """Helper limits container."""

    max_severity: str = "INFO"

    model_config = ConfigDict(frozen=True)


class DashboardSnapshot(BaseModel):
    """Aggregated snapshot metrics dashboard report."""

    snapshot_id: str
    health_reports: List[HealthReport] = Field(default_factory=list)
    alerts_count: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class ComponentMetrics(BaseModel):
    """Component counts totals."""

    component_name: str
    calls_count: int
    errors_count: int

    model_config = ConfigDict(frozen=True)


class LatencyMeasurement(BaseModel):
    """Execution timing latencies distribution stats."""

    metric_name: str
    min_ms: float
    max_ms: float
    mean_ms: float
    p95_ms: float
    p99_ms: float

    model_config = ConfigDict(frozen=True)


class ErrorReport(BaseModel):
    """Error logs diagnostics wrapper."""

    error_id: str
    subsystem: str
    message: str
    stack_trace: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class PerformanceProfile(BaseModel):
    """Resource load profiles."""

    cpu_load_pct: float
    memory_used_mb: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)
