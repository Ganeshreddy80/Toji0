"""PostgreSQL monitoring repository.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from research_platform.persistence.postgres.base_repository import BaseRepository
from research_platform.persistence.postgres.migrations import MonitoringStatusModel, MonitoringAlertModel, MonitoringMetricModel
from research_platform.monitoring.models import ServiceStatus, AlertCard, MetricCounter


class PostgresMonitoringRepository(BaseRepository):
    """PostgreSQL-backed Monitoring telemetry repository."""

    def __init__(self, session_manager) -> None:
        super().__init__(session_manager, MonitoringStatusModel)
        self._alert_repo = BaseRepository(session_manager, MonitoringAlertModel)
        self._metric_repo = BaseRepository(session_manager, MonitoringMetricModel)

    def save_status(self, status: ServiceStatus) -> None:
        model = self.get(status.service_name)
        if model:
            updates = {
                "response_time_ms": status.response_time_ms,
                "is_alive": status.is_alive,
                "last_check": status.last_heartbeat
            }
            self.update(status.service_name, updates)
        else:
            new_model = MonitoringStatusModel(
                service_name=status.service_name,
                response_time_ms=status.response_time_ms,
                is_alive=status.is_alive,
                last_check=status.last_heartbeat
            )
            self.create(new_model)

    def get_status(self, service_name: str) -> Optional[ServiceStatus]:
        model = self.get(service_name)
        if model:
            return ServiceStatus(
                service_name=model.service_name,
                response_time_ms=model.response_time_ms,
                is_alive=model.is_alive,
                last_heartbeat=model.last_check
            )
        return None

    def save_alert(self, alert: AlertCard) -> None:
        model = self._alert_repo.get(alert.alert_id)
        if model:
            updates = {
                "level": alert.level,
                "source": alert.source,
                "message": alert.message,
                "timestamp": alert.timestamp
            }
            self._alert_repo.update(alert.alert_id, updates)
        else:
            new_model = MonitoringAlertModel(
                alert_id=alert.alert_id,
                level=alert.level,
                source=alert.source,
                message=alert.message,
                timestamp=alert.timestamp
            )
            self._alert_repo.create(new_model)

    def get_alert(self, alert_id: str) -> Optional[AlertCard]:
        model = self._alert_repo.get(alert_id)
        if model:
            return AlertCard(
                alert_id=model.alert_id,
                level=model.level,
                source=model.source,
                message=model.message,
                timestamp=model.timestamp
            )
        return None

    def save_metric(self, metric: MetricCounter) -> None:
        model = self._metric_repo.get(metric.metric_name)
        if model:
            self._metric_repo.update(metric.metric_name, {"value": metric.value})
        else:
            new_model = MonitoringMetricModel(metric_name=metric.metric_name, value=metric.value)
            self._metric_repo.create(new_model)

    def get_metric(self, metric_name: str) -> Optional[MetricCounter]:
        model = self._metric_repo.get(metric_name)
        if model:
            return MetricCounter(metric_name=model.metric_name, value=model.value)
        return None
