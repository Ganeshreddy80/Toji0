"""Abstract contracts for the Monitoring Center.
"""

from __future__ import annotations

import abc
from typing import Optional
from research_platform.monitoring.models import ServiceStatus, AlertCard, MetricCounter


class IMonitoringRepository(abc.ABC):
    """Abstract contract for persisting monitoring state metrics."""

    @abc.abstractmethod
    def save_status(self, status: ServiceStatus) -> None:
        """Persist service status details."""

    @abc.abstractmethod
    def get_status(self, service_name: str) -> Optional[ServiceStatus]:
        """Retrieve status details by service name."""

    @abc.abstractmethod
    def save_alert(self, alert: AlertCard) -> None:
        """Persist system alerts warning cards."""

    @abc.abstractmethod
    def get_alert(self, alert_id: str) -> Optional[AlertCard]:
        """Retrieve warning alert details by ID."""

    @abc.abstractmethod
    def save_metric(self, metric: MetricCounter) -> None:
        """Persist metric counters values."""

    @abc.abstractmethod
    def get_metric(self, metric_name: str) -> Optional[MetricCounter]:
        """Retrieve metric details by name."""
