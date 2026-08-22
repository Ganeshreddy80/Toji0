"""Event contracts for the Observability Platform.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class MetricRecorded(BaseEvent):
    """Fired when metrics engine saves a counter/gauge value."""
    pass


@dataclass(frozen=True)
class LogRecorded(BaseEvent):
    """Fired when structured logger saves an error/warning."""
    pass


@dataclass(frozen=True)
class TraceStarted(BaseEvent):
    """Fired when parent tracing span initiates."""
    pass


@dataclass(frozen=True)
class TraceCompleted(BaseEvent):
    """Fired when child tracing span closes."""
    pass


@dataclass(frozen=True)
class HealthCheckStarted(BaseEvent):
    """Fired when components status sweeps begin."""
    pass


@dataclass(frozen=True)
class HealthCheckCompleted(BaseEvent):
    """Fired when component status reports save."""
    pass


@dataclass(frozen=True)
class AlertGenerated(BaseEvent):
    """Fired when anomalies are detected."""
    pass


@dataclass(frozen=True)
class AlertAcknowledged(BaseEvent):
    """Fired when warning notifications clear."""
    pass


@dataclass(frozen=True)
class ComponentHealthy(BaseEvent):
    """Fired when component status restores to healthy."""
    pass


@dataclass(frozen=True)
class ComponentUnhealthy(BaseEvent):
    """Fired when components report errors threshold breach."""
    pass


@dataclass(frozen=True)
class PerformanceWarning(BaseEvent):
    """Fired when latency measurements exceed P95 bounds."""
    pass
