"""Thread-safe Operations Manager orchestrating metrics, alerting, audit, dashboards, and reporting (Sprint 12C)."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from operations.alert_manager import AlertManager, AlertRecord, AlertStatus
from operations.alert_rules import AlertRule, AlertSeverity, ComparisonOperator
from operations.audit_logger import AuditEntry, AuditLogger
from operations.metrics_collector import MetricSnapshot, MetricsCollector
from operations.metrics_repository import MetricsRepository
from operations.operations_dashboard import DashboardView, OperationsDashboard
from operations.operations_events import (
    AlertAcknowledged,
    AlertResolved,
    AlertTriggered,
    AuditEntryCreated,
    DashboardGenerated,
    MetricsCollected,
    OperationsCycleCompleted,
    ReportGenerated,
)
from operations.operations_reports import OperationsReport, OperationsReports, ReportType
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class OperationsManager:
    """Thread-safe Operations Manager orchestrating operational visibility, alerting, auditing, and reporting."""

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        collector: Optional[MetricsCollector] = None,
        metrics_repository: Optional[MetricsRepository] = None,
        alert_manager: Optional[AlertManager] = None,
        audit_logger: Optional[AuditLogger] = None,
        dashboard: Optional[OperationsDashboard] = None,
        reports: Optional[OperationsReports] = None,
        deployment_manager: Optional[Any] = None,
        health_monitor: Optional[Any] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._collector = collector or MetricsCollector()
        self._metrics_repo = metrics_repository or MetricsRepository()
        self._alert_mgr = alert_manager or AlertManager()
        self._audit_logger = audit_logger or AuditLogger()
        self._dashboard = dashboard or OperationsDashboard()
        self._reports = reports or OperationsReports()

        self._dep_mgr = deployment_manager
        self._health_monitor = health_monitor

    def collect_metrics(
        self,
        cpu_utilization: float = 25.0,
        memory_utilization: float = 40.0,
        disk_utilization: float = 55.0,
        network_throughput_mbps: float = 120.0,
        deployment_count: int = 1,
        service_health_pct: float = 100.0,
        application_latency_ms: float = 12.5,
        request_throughput_rps: float = 450.0,
        extra_labels: Optional[Dict[str, str]] = None,
    ) -> List[MetricSnapshot]:
        """Collect system metrics, store in repository, evaluate alerts, and publish event."""
        with self._lock:
            snapshots = self._collector.collect_system_metrics(
                cpu_utilization=cpu_utilization,
                memory_utilization=memory_utilization,
                disk_utilization=disk_utilization,
                network_throughput_mbps=network_throughput_mbps,
                deployment_count=deployment_count,
                service_health_pct=service_health_pct,
                application_latency_ms=application_latency_ms,
                request_throughput_rps=request_throughput_rps,
                extra_labels=extra_labels,
            )
            self._metrics_repo.add_snapshots(snapshots)

            if self._event_bus:
                self._event_bus.publish(
                    MetricsCollected(
                        metric_count=len(snapshots),
                    )
                )

            # Auto-evaluate alerts on collection
            self.evaluate_alerts()

            return snapshots

    def evaluate_alerts(self) -> List[AlertRecord]:
        """Evaluate alert rules against metrics repository and publish AlertTriggered events."""
        with self._lock:
            new_alerts = self._alert_mgr.evaluate_metrics(self._metrics_repo)
            if self._event_bus:
                for a in new_alerts:
                    self._event_bus.publish(
                        AlertTriggered(
                            alert_id=a.alert_id,
                            rule_name=a.rule_name,
                            metric_name=a.metric_name,
                            severity=a.severity.value,
                            current_value=a.current_value,
                            threshold_value=a.threshold_value,
                        )
                    )
            return new_alerts

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "operator") -> AlertRecord:
        """Acknowledge an operational alert."""
        with self._lock:
            rec = self._alert_mgr.acknowledge_alert(alert_id, acknowledged_by)
            if self._event_bus:
                self._event_bus.publish(
                    AlertAcknowledged(
                        alert_id=alert_id,
                        acknowledged_by=acknowledged_by,
                    )
                )
            return rec

    def resolve_alert(self, alert_id: str, resolution_note: str = "Condition normalized") -> AlertRecord:
        """Resolve an operational alert."""
        with self._lock:
            rec = self._alert_mgr.resolve_alert(alert_id, resolution_note)
            if self._event_bus:
                self._event_bus.publish(
                    AlertResolved(
                        alert_id=alert_id,
                        resolution_note=resolution_note,
                    )
                )
            return rec

    def record_audit(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        actor: str = "system",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Record an immutable audit entry and publish event."""
        with self._lock:
            entry = self._audit_logger.record_entry(action, resource_type, resource_id, actor, details)
            if self._event_bus:
                self._event_bus.publish(
                    AuditEntryCreated(
                        entry_id=entry.entry_id,
                        action=action,
                        actor=actor,
                        resource_type=resource_type,
                        resource_id=resource_id,
                    )
                )
            return entry

    def generate_dashboard(self) -> DashboardView:
        """Generate advisory dashboard view and publish event."""
        with self._lock:
            view = self._dashboard.generate_dashboard(
                self._metrics_repo,
                self._alert_mgr,
                self._audit_logger,
                self._dep_mgr,
                self._health_monitor,
            )
            if self._event_bus:
                self._event_bus.publish(
                    DashboardGenerated(
                        view_id=view.view_id,
                        overall_status=view.overall_status,
                    )
                )
            return view

    def generate_report(self, report_type: ReportType = ReportType.SUMMARY) -> OperationsReport:
        """Generate an operational report and publish event."""
        with self._lock:
            if report_type == ReportType.SUMMARY:
                report = self._reports.generate_operational_summary(
                    self._metrics_repo, self._alert_mgr, self._audit_logger, self._dep_mgr, self._health_monitor
                )
            elif report_type == ReportType.DEPLOYMENT:
                report = self._reports.generate_deployment_history_report(self._dep_mgr)
            elif report_type == ReportType.ALERT:
                report = self._reports.generate_alert_history_report(self._alert_mgr)
            elif report_type == ReportType.HEALTH:
                report = self._reports.generate_health_overview_report(self._health_monitor)
            elif report_type == ReportType.AUDIT:
                report = self._reports.generate_audit_overview_report(self._audit_logger)
            else:
                report = self._reports.generate_operational_summary(
                    self._metrics_repo, self._alert_mgr, self._audit_logger, self._dep_mgr, self._health_monitor
                )

            if self._event_bus:
                self._event_bus.publish(
                    ReportGenerated(
                        report_id=report.report_id,
                        report_type=report.report_type.value,
                    )
                )
            return report

    def run_operations_cycle(
        self,
        cpu: float = 30.0,
        mem: float = 45.0,
        disk: float = 50.0,
    ) -> Tuple[List[MetricSnapshot], List[AlertRecord], DashboardView]:
        """Execute a full operational cycle: collect, evaluate, generate dashboard, and publish completion event."""
        with self._lock:
            snapshots = self.collect_metrics(
                cpu_utilization=cpu,
                memory_utilization=mem,
                disk_utilization=disk,
            )
            alerts = self.evaluate_alerts()
            dash = self.generate_dashboard()

            if self._event_bus:
                self._event_bus.publish(
                    OperationsCycleCompleted(
                        metrics_count=len(snapshots),
                        active_alerts_count=len(self._alert_mgr.get_active_alerts()),
                        overall_health=dash.overall_status,
                    )
                )
            return snapshots, alerts, dash

    # Component Accessors
    @property
    def collector(self) -> MetricsCollector:
        return self._collector

    @property
    def metrics_repository(self) -> MetricsRepository:
        return self._metrics_repo

    @property
    def alert_manager(self) -> AlertManager:
        return self._alert_mgr

    @property
    def audit_logger(self) -> AuditLogger:
        return self._audit_logger

    @property
    def dashboard(self) -> OperationsDashboard:
        return self._dashboard

    @property
    def reports(self) -> OperationsReports:
        return self._reports

    def clear(self) -> None:
        """Clear all in-memory operational repositories."""
        with self._lock:
            self._metrics_repo.clear()
            self._alert_mgr.clear()
            self._audit_logger.clear()
