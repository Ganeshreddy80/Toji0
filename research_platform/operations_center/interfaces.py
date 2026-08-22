"""Abstract contracts for the Institutional Operations Center.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional
from research_platform.operations_center.dashboard_models import (
    AlertCard,
    DashboardSnapshot,
)


class IOperationsRepository(abc.ABC):
    """Abstract contract for caching rolling summaries and alerts logs."""

    @abc.abstractmethod
    def save_snapshot(self, snapshot: DashboardSnapshot) -> None:
        """Cache a dashboard snapshot in memory and rolling histories."""

    @abc.abstractmethod
    def get_latest_snapshot(self) -> Optional[DashboardSnapshot]:
        """Retrieve the most recent dashboard snapshot."""

    @abc.abstractmethod
    def list_historical_snapshots(self) -> List[DashboardSnapshot]:
        """Retrieve rolling snapshot list."""

    @abc.abstractmethod
    def save_alert(self, alert: AlertCard) -> None:
        """Cache active alerts."""

    @abc.abstractmethod
    def list_active_alerts(self) -> List[AlertCard]:
        """List active priority alerts."""


class IOperationsOrchestrator(abc.ABC):
    """Abstract contract for orchestrating real-time operations dashboards refreshes."""

    @abc.abstractmethod
    def compile_dashboard_snapshot(self) -> DashboardSnapshot:
        """Aggregate states across all active core systems."""
