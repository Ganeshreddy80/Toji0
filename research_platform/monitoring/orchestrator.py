"""Monitoring Center orchestrator coordinating heartbeats, alert notifications, and metrics aggregation.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.monitoring.models import (
    ServiceStatus,
    AlertCard,
    MetricCounter,
)
from research_platform.monitoring.repository import MonitoringRepository
from research_platform.monitoring.health_engine import HealthEngine
from research_platform.monitoring.alert_engine import AlertEngine
from research_platform.monitoring.metrics_engine import MetricsEngine
from research_platform.monitoring.events import AlertTriggered

logger = logging.getLogger(__name__)


class MonitoringOrchestrator:
    """Central orchestrator managing platform health statuses and telemetry."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = MonitoringRepository()
        self._health = HealthEngine()
        self._alert = AlertEngine()
        self._metrics = MetricsEngine()

    @property
    def repository(self) -> MonitoringRepository:
        return self._repo

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("MonitoringCenter: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── Actions ──────────────────────────────────────────────────────

    def check_health(self, service_name: str, response_time_ms: float) -> ServiceStatus:
        status = self._health.evaluate_heartbeat(service_name, response_time_ms)
        self._repo.save_status(status)
        return status

    def trigger_alert(self, alert_id: str, level: str, source: str, message: str) -> AlertCard:
        alert = self._alert.compile_alert(alert_id, level, source, message)
        self._repo.save_alert(alert)
        
        self._event_bus.publish(AlertTriggered(payload={"alert_id": alert_id}))
        self._log_downstream_registries(alert_id, "MONITORING_ALERT", f"Alert Triggered: level={level} source={source} message={message}")
        return alert

    def increment_metric_counter(self, metric_name: str, increment: int = 1) -> MetricCounter:
        curr = self._repo.get_metric(metric_name)
        val = curr.value if curr else 0
        new_val = self._metrics.increment_metric(val, increment)
        
        updated = MetricCounter(metric_name=metric_name, value=new_val)
        self._repo.save_metric(updated)
        return updated

    def _log_downstream_registries(self, ref_id: str, element_type: str, message: str) -> None:
        # 1. Institutional Memory (R16)
        mem = self._get_memory_orchestrator()
        if mem:
            try:
                mem.publish_memory("observability", {
                    "ref_id": ref_id,
                    "type": element_type,
                    "message": message
                })
            except Exception as e:
                logger.error("Monitoring Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=ref_id,
                    node_type=element_type,
                    subsystem="monitoring",
                    event="MonitoringUpdated",
                    author="monitoring",
                    properties={"message": message}
                )
            except Exception as e:
                logger.error("Monitoring Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("Monitoring: Failed to refresh operations center: %s", e)
