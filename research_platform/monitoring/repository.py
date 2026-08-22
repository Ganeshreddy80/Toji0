"""Monitoring telemetry repository with PostgreSQL delegation and memory fallbacks.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional
from research_platform.monitoring.interfaces import IMonitoringRepository
from research_platform.monitoring.models import ServiceStatus, AlertCard, MetricCounter
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.monitoring_repository import PostgresMonitoringRepository


class MonitoringRepository(IMonitoringRepository):
    """Memory-backed repository with PostgreSQL delegation capabilities."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._statuses: Dict[str, ServiceStatus] = {}
        self._alerts: Dict[str, AlertCard] = {}
        self._metrics: Dict[str, MetricCounter] = {}

    def _get_pg_repo(self) -> Optional[PostgresMonitoringRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresMonitoringRepository(session_manager)
        return None

    def save_status(self, status: ServiceStatus) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_status(status)
            
        with self._lock:
            self._statuses[status.service_name] = status

    def get_status(self, service_name: str) -> Optional[ServiceStatus]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_status(service_name)
            
        with self._lock:
            return self._statuses.get(service_name)

    def save_alert(self, alert: AlertCard) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_alert(alert)
            
        with self._lock:
            self._alerts[alert.alert_id] = alert

    def get_alert(self, alert_id: str) -> Optional[AlertCard]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_alert(alert_id)
            
        with self._lock:
            return self._alerts.get(alert_id)

    def save_metric(self, metric: MetricCounter) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_metric(metric)
            
        with self._lock:
            self._metrics[metric.metric_name] = metric

    def get_metric(self, metric_name: str) -> Optional[MetricCounter]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_metric(metric_name)
            
        with self._lock:
            return self._metrics.get(metric_name)
