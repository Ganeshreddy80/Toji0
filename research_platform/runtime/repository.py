"""Thread-safe runtime repository caching execution metrics and heartbeats.
"""

from __future__ import annotations

import threading
from typing import Dict, Any, Optional
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.monitoring_repository import PostgresMonitoringRepository


class RuntimeRepository:
    """Thread-safe repository storing loop execution latencies, event logs, and heartbeats."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics: Dict[str, Any] = {}
        self._heartbeats: Dict[str, Any] = {}

    def _get_pg_repo(self) -> Optional[PostgresMonitoringRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresMonitoringRepository(session_manager)
        return None

    def save_metric(self, name: str, value: Any) -> None:
        with self._lock:
            self._metrics[name] = value

        pg_repo = self._get_pg_repo()
        if pg_repo:
            from research_platform.monitoring.models import MetricCounter
            # Save into monitoring metrics table
            try:
                pg_repo.save_metric(MetricCounter(metric_name=name, value=int(float(value))))
            except Exception:
                pass  # Fallback gracefully under database disruptions

    def get_metric(self, name: str) -> Optional[Any]:
        with self._lock:
            return self._metrics.get(name)

    def save_heartbeat(self, status: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._heartbeats[status] = payload

        pg_repo = self._get_pg_repo()
        if pg_repo:
            from research_platform.monitoring.models import ServiceStatus
            try:
                # Map runtime heartbeat to ServiceStatus record
                serv = ServiceStatus(
                    service_name=f"Runtime_{status}",
                    is_alive=True,
                    response_time_ms=payload.get("loop_latency_ms", 0.0)
                )
                pg_repo.save_status(serv)
            except Exception:
                pass

    def get_latest_heartbeat(self, status: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._heartbeats.get(status)
