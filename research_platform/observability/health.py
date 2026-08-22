"""Health Engine tracking components status.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List

from research_platform.observability.models import HealthReport, HealthStatus


class HealthEngine:
    """Monitors component status and aggregates health report metrics."""

    def __init__(self) -> None:
        self._statuses: Dict[str, HealthStatus] = {}

    def update_status(self, component: str, healthy: bool, details: str = None) -> HealthStatus:
        status = HealthStatus(
            component_name=component,
            healthy=healthy,
            details=details
        )
        self._statuses[component] = status
        return status

    def compile_report(self) -> HealthReport:
        return HealthReport(
            report_id=str(uuid.uuid4()),
            statuses=list(self._statuses.values())
        )
