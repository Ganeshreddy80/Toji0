"""Universe health and observability monitor.

Tracks staleness, coverage, filter pass rates, tier distribution,
drift counts, and per-provider status to report overall health.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from toji_platform.core.types import HealthStatus
from universe.core.models import UniverseSnapshot

logger = logging.getLogger(__name__)


class UniverseHealthMonitor:
    """Monitor universe scan health and compute aggregate metrics.

    Health Rules:
    - HEALTHY: recent scan, >0 assets, all providers ok
    - DEGRADED: scan is stale OR some providers failing
    - UNHEALTHY: no scans OR all providers down
    """

    def __init__(self, staleness_threshold_seconds: int = 28800) -> None:
        """Initialize the health monitor.

        Args:
            staleness_threshold_seconds: Maximum age of last scan before
                reporting degraded. Default: 8 hours (2x scan interval).
        """
        self._staleness_threshold = staleness_threshold_seconds
        self._last_snapshot: UniverseSnapshot | None = None
        self._provider_statuses: dict[str, str] = {}

    def update(
        self,
        snapshot: UniverseSnapshot,
        provider_statuses: dict[str, str] | None = None,
    ) -> None:
        """Update the monitor with the latest scan results."""
        self._last_snapshot = snapshot
        if provider_statuses:
            self._provider_statuses = provider_statuses

    def health_check(self) -> HealthStatus:
        """Compute overall universe health status."""
        if not self._last_snapshot:
            return HealthStatus.UNHEALTHY

        # Check staleness
        now = datetime.now(UTC)
        elapsed = (now - self._last_snapshot.scanned_at).total_seconds()
        if elapsed > self._staleness_threshold:
            return HealthStatus.DEGRADED

        # Check provider health
        if self._provider_statuses:
            error_count = sum(
                1 for s in self._provider_statuses.values()
                if s.startswith("error")
            )
            if error_count == len(self._provider_statuses):
                return HealthStatus.UNHEALTHY
            if error_count > 0:
                return HealthStatus.DEGRADED

        # Check asset count
        if self._last_snapshot.total_after_filter == 0:
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def get_metrics(self) -> dict[str, Any]:
        """Return detailed health metrics."""
        if not self._last_snapshot:
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "last_scan_at": None,
                "total_discovered": 0,
                "total_after_filter": 0,
                "tier_distribution": {},
                "drift_count": 0,
                "provider_health": {},
            }

        return {
            "status": self.health_check().value,
            "last_scan_at": self._last_snapshot.scanned_at.isoformat(),
            "total_discovered": self._last_snapshot.total_discovered,
            "total_after_filter": self._last_snapshot.total_after_filter,
            "tier_distribution": self._last_snapshot.tier_distribution,
            "drift_count": self._last_snapshot.drift_count,
            "provider_health": self._provider_statuses,
        }
