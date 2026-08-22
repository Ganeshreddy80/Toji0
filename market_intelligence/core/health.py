"""Health Monitor for aggregating engine statuses and dependency health metrics."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from market_intelligence.core.enums import HealthState, ReplayStatus
from market_intelligence.core.events import HealthReportGenerated
from market_intelligence.core.models import HealthReport
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Aggregates sub-engine health statuses, dependency failures, latency and replay state."""

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus
        # Default statuses
        self._engine_statuses: dict[str, HealthState] = {
            "core_analysis_engine": HealthState.HEALTHY,
            "confidence_engine": HealthState.HEALTHY,
            "story_generator": HealthState.HEALTHY,
        }
        self._dependency_failures: list[str] = []
        self._last_update = datetime.now(timezone.utc)
        self._processing_latency_ms = 0.0
        self._replay_status = ReplayStatus.PENDING

    def set_engine_status(self, engine_name: str, status: HealthState) -> None:
        """Update health status for a specific sub-engine."""
        self._engine_statuses[engine_name] = status
        self._last_update = datetime.now(timezone.utc)

    def add_dependency_failure(self, dependency: str) -> None:
        """Register a dependency failure (e.g. database disconnect)."""
        if dependency not in self._dependency_failures:
            self._dependency_failures.append(dependency)
        self._last_update = datetime.now(timezone.utc)

    def remove_dependency_failure(self, dependency: str) -> None:
        """Remove a dependency failure registration."""
        if dependency in self._dependency_failures:
            self._dependency_failures.remove(dependency)
        self._last_update = datetime.now(timezone.utc)

    def clear_dependency_failures(self) -> None:
        """Clear all dependency failures."""
        self._dependency_failures.clear()

    def set_replay_status(self, status: ReplayStatus) -> None:
        """Update the latest replay verification status."""
        self._replay_status = status

    def set_processing_latency(self, latency_ms: float) -> None:
        """Update the latest processing latency metric."""
        self._processing_latency_ms = latency_ms

    def get_report(self) -> HealthReport:
        """Compile and return health report, publishing an update event."""
        # Determine overall status
        # If any engine is FAILED or we have dependency failures, overall status is FAILED
        # If any engine is DEGRADED, overall status is DEGRADED
        # Otherwise, overall status is HEALTHY
        overall_status = HealthState.HEALTHY

        if self._dependency_failures or any(
            status == HealthState.FAILED for status in self._engine_statuses.values()
        ):
            overall_status = HealthState.FAILED
        elif any(
            status == HealthState.DEGRADED for status in self._engine_statuses.values()
        ):
            overall_status = HealthState.DEGRADED

        report = HealthReport(
            engine_statuses=self._engine_statuses.copy(),
            dependency_failures=list(self._dependency_failures),
            last_update=self._last_update,
            processing_latency_ms=self._processing_latency_ms,
            replay_status=self._replay_status,
            overall_status=overall_status,
            timestamp=datetime.now(timezone.utc),
        )

        self._publish_event(report)
        return report

    def _publish_event(self, report: HealthReport) -> None:
        if self._event_bus is None:
            return

        payload = {
            "overall_status": report.overall_status.value,
            "engine_statuses": {k: v.value for k, v in report.engine_statuses.items()},
            "dependency_failures": report.dependency_failures,
            "last_update": report.last_update.isoformat(),
            "processing_latency_ms": report.processing_latency_ms,
            "replay_status": report.replay_status.value,
        }

        event = HealthReportGenerated(
            source="market_intelligence.health_monitor",
            payload=payload,
        )
        self._event_bus.publish(event)
