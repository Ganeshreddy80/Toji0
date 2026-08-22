"""Operations Report Generator creating immutable advisory operational reports (Sprint 12C)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from operations.alert_manager import AlertManager
from operations.audit_logger import AuditLogger
from operations.metrics_repository import MetricsRepository

logger = logging.getLogger(__name__)


class ReportType(str, Enum):
    """Supported operational report categories."""

    SUMMARY = "SUMMARY"
    DEPLOYMENT = "DEPLOYMENT"
    ALERT = "ALERT"
    HEALTH = "HEALTH"
    AUDIT = "AUDIT"


class OperationsReport(BaseModel):
    """Immutable operational report model."""

    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    report_type: ReportType = Field(default=ReportType.SUMMARY)
    title: str = Field(..., description="Report title.")
    content: Dict[str, Any] = Field(default_factory=dict, description="Report payload content.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class OperationsReports:
    """Generator producing immutable advisory reports for operational domains."""

    def generate_operational_summary(
        self,
        metrics_repo: MetricsRepository,
        alert_mgr: AlertManager,
        audit_logger: AuditLogger,
        dep_mgr: Optional[Any] = None,
        health_monitor: Optional[Any] = None,
    ) -> OperationsReport:
        """Generate high-level operational summary report."""
        cpu = metrics_repo.aggregate_metric("cpu_utilization")
        mem = metrics_repo.aggregate_metric("memory_utilization")

        content = {
            "metrics": {
                "total_snapshots": metrics_repo.count(),
                "cpu_utilization_mean": cpu.mean_value if cpu else 0.0,
                "memory_utilization_mean": mem.mean_value if mem else 0.0,
            },
            "alerts": {
                "active": len(alert_mgr.get_active_alerts()),
                "total_history": len(alert_mgr.get_alert_history()),
            },
            "audit": {
                "total_entries": audit_logger.count(),
            },
            "deployments_count": dep_mgr.count() if dep_mgr and hasattr(dep_mgr, "count") else 0,
        }

        return OperationsReport(
            report_type=ReportType.SUMMARY,
            title="Operational Summary Report",
            content=content,
        )

    def generate_deployment_history_report(self, dep_mgr: Optional[Any] = None) -> OperationsReport:
        """Generate deployment history report."""
        deployments_data = []
        if dep_mgr and hasattr(dep_mgr, "list_deployments"):
            for d in dep_mgr.list_deployments():
                deployments_data.append({
                    "deployment_id": d.deployment_id,
                    "service_name": d.service_name,
                    "version": d.version,
                    "status": d.status.value if hasattr(d.status, "value") else str(d.status),
                    "created_at": d.created_at.isoformat(),
                })

        return OperationsReport(
            report_type=ReportType.DEPLOYMENT,
            title="Deployment History Report",
            content={
                "total_deployments": len(deployments_data),
                "deployments": deployments_data,
            },
        )

    def generate_alert_history_report(self, alert_mgr: AlertManager) -> OperationsReport:
        """Generate alert history report."""
        alerts = alert_mgr.get_alert_history()
        alerts_data = [
            {
                "alert_id": a.alert_id,
                "rule_name": a.rule_name,
                "severity": a.severity.value,
                "status": a.status.value,
                "current_value": a.current_value,
                "threshold_value": a.threshold_value,
                "triggered_at": a.triggered_at.isoformat(),
            }
            for a in alerts
        ]

        return OperationsReport(
            report_type=ReportType.ALERT,
            title="Alert History Report",
            content={
                "total_alerts": len(alerts_data),
                "alerts": alerts_data,
            },
        )

    def generate_health_overview_report(self, health_monitor: Optional[Any] = None) -> OperationsReport:
        """Generate health overview report."""
        if health_monitor and hasattr(health_monitor, "generate_health_report"):
            content = health_monitor.generate_health_report()
        else:
            content = {"status": "NO_HEALTH_MONITOR_CONNECTED"}

        return OperationsReport(
            report_type=ReportType.HEALTH,
            title="Health Overview Report",
            content=content,
        )

    def generate_audit_overview_report(self, audit_logger: AuditLogger) -> OperationsReport:
        """Generate audit overview report."""
        entries = audit_logger.get_entries()
        entries_data = [
            {
                "entry_id": e.entry_id,
                "action": e.action,
                "actor": e.actor,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in entries
        ]

        return OperationsReport(
            report_type=ReportType.AUDIT,
            title="Audit Overview Report",
            content={
                "total_entries": len(entries_data),
                "audit_entries": entries_data,
            },
        )
