"""Operations Dashboard generating advisory status summaries (Sprint 12C)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from operations.alert_manager import AlertManager
from operations.audit_logger import AuditLogger
from operations.metrics_repository import MetricsRepository

logger = logging.getLogger(__name__)


class DashboardView(BaseModel):
    """Immutable advisory dashboard summary view model."""

    view_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    overall_status: str = Field(default="HEALTHY", description="Overall system health status.")
    deployment_summary: Dict[str, Any] = Field(default_factory=dict)
    service_summary: Dict[str, Any] = Field(default_factory=dict)
    alert_summary: Dict[str, Any] = Field(default_factory=dict)
    health_summary: Dict[str, Any] = Field(default_factory=dict)
    metrics_summary: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class OperationsDashboard:
    """Generates advisory operational dashboard views consolidating metrics, alerts, health, and deployment status."""

    def generate_dashboard(
        self,
        metrics_repo: MetricsRepository,
        alert_mgr: AlertManager,
        audit_logger: AuditLogger,
        dep_mgr: Optional[Any] = None,
        health_monitor: Optional[Any] = None,
    ) -> DashboardView:
        """Generate a complete advisory DashboardView snapshot."""
        # 1. Metrics Summary
        cpu_agg = metrics_repo.aggregate_metric("cpu_utilization")
        mem_agg = metrics_repo.aggregate_metric("memory_utilization")

        metrics_summary = {
            "total_metric_snapshots": metrics_repo.count(),
            "cpu_mean_pct": cpu_agg.mean_value if cpu_agg else 0.0,
            "memory_mean_pct": mem_agg.mean_value if mem_agg else 0.0,
        }

        # 2. Alert Summary
        active_alerts = alert_mgr.get_active_alerts()
        all_alerts = alert_mgr.get_alert_history()
        critical_count = sum(1 for a in active_alerts if a.severity.value == "CRITICAL")

        alert_summary = {
            "total_recorded_alerts": len(all_alerts),
            "active_alerts_count": len(active_alerts),
            "critical_active_count": critical_count,
            "has_critical_alerts": critical_count > 0,
        }

        # 3. Health Summary
        if health_monitor and hasattr(health_monitor, "generate_health_report"):
            health_summary = health_monitor.generate_health_report()
        else:
            health_summary = {"status": "UNKNOWN", "total_services": 0}

        # 4. Service Summary
        if dep_mgr and hasattr(dep_mgr, "registry"):
            service_summary = {
                "total_registered_services": dep_mgr.registry.count(),
            }
        else:
            service_summary = {"total_registered_services": 0}

        # 5. Deployment Summary
        if dep_mgr and hasattr(dep_mgr, "count"):
            deployment_summary = {
                "total_deployments": dep_mgr.count(),
            }
        else:
            deployment_summary = {"total_deployments": 0}

        # Overall status determination
        overall_status = "HEALTHY"
        if critical_count > 0 or health_summary.get("overall_status") == "DEGRADED":
            overall_status = "DEGRADED"

        view = DashboardView(
            overall_status=overall_status,
            deployment_summary=deployment_summary,
            service_summary=service_summary,
            alert_summary=alert_summary,
            health_summary=health_summary,
            metrics_summary=metrics_summary,
        )

        logger.info("Generated Operations Dashboard view '%s' (overall_status=%s)", view.view_id, overall_status)
        return view
