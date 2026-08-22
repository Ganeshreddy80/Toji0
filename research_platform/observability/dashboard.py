"""Dashboard API compiling operational summaries and snapshots.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from research_platform.observability.models import DashboardSnapshot, HealthReport


class ObservabilityDashboardApi:
    """Aggregates metrics and health reports for dashboard layouts."""

    @staticmethod
    def compile_snapshot(reports: List[HealthReport], alerts_count: int) -> DashboardSnapshot:
        return DashboardSnapshot(
            snapshot_id=str(uuid.uuid4()),
            health_reports=reports,
            alerts_count=alerts_count
        )
