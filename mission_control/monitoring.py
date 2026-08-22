"""Thread-safe Main Monitoring Manager & Event Orchestrator for Mission Control (Sprint 10B)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from mission_control.dashboard_renderer import DashboardRenderer, DashboardSnapshot
from mission_control.history import BoundedHistory, HealthTransitionRecord
from mission_control.log_monitor import LogLevel, LogMonitor
from mission_control.notification_manager import NotificationCategory, NotificationManager
from mission_control.reports import ReportGenerator, SystemStatusReport
from mission_control.resource_monitor import ResourceMonitor, ResourceSnapshot
from mission_control.system_monitor import ServiceHealthStatus, ServiceRegistration, SystemMonitor
from mission_control.trend_analyzer import TrendAnalyzer
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


# Standard Monitoring Events
class MonitoringStarted(BaseModel):
    """Event emitted when monitoring manager is started."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="MonitoringStarted")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class MonitoringStopped(BaseModel):
    """Event emitted when monitoring manager is stopped."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="MonitoringStopped")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class DashboardUpdated(BaseModel):
    """Event emitted when dashboard snapshot is generated."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="DashboardUpdated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    snapshot: DashboardSnapshot = Field(..., description="Dashboard snapshot.")

    model_config = ConfigDict(frozen=True)


class AlertGenerated(BaseModel):
    """Event emitted when a system alert is triggered."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="AlertGenerated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    alert_type: str = Field(..., description="Classification category/type.")
    severity: str = Field(..., description="Severity level.")
    message: str = Field(..., description="Alert description.")
    service_name: str = Field(default="system", description="Service identifier.")

    model_config = ConfigDict(frozen=True)


class NotificationSent(BaseModel):
    """Event emitted when a notification is dispatched."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="NotificationSent")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    category: str = Field(..., description="Notification category.")
    title: str = Field(..., description="Notification title.")
    message: str = Field(..., description="Notification content.")
    target_service: str = Field(default="system", description="Target service name.")

    model_config = ConfigDict(frozen=True)


class ResourceThresholdExceeded(BaseModel):
    """Event emitted when a resource threshold is breached."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="ResourceThresholdExceeded")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resource_type: str = Field(..., description="CPU or Memory identifier.")
    value: float = Field(..., description="Measured resource value.")
    threshold: float = Field(..., description="Threshold limit value.")
    message: str = Field(..., description="Exceeded limit message.")

    model_config = ConfigDict(frozen=True)


class MonitoringManager:
    """Thread-safe Main Monitoring Manager orchestrating system, resource, log, notification, and dashboard components."""

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        system_monitor: Optional[SystemMonitor] = None,
        resource_monitor: Optional[ResourceMonitor] = None,
        log_monitor: Optional[LogMonitor] = None,
        notification_manager: Optional[NotificationManager] = None,
        trend_analyzer: Optional[TrendAnalyzer] = None,
        dashboard_renderer: Optional[DashboardRenderer] = None,
        history: Optional[BoundedHistory] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._is_running: bool = False

        self._system_monitor = system_monitor or SystemMonitor()
        self._resource_monitor = resource_monitor or ResourceMonitor()
        self._log_monitor = log_monitor or LogMonitor()
        self._notification_mgr = notification_manager or NotificationManager()
        self._trend_analyzer = trend_analyzer or TrendAnalyzer()
        self._dashboard_renderer = dashboard_renderer or DashboardRenderer()
        self._history = history or BoundedHistory()

        self._active_alerts: List[Dict[str, Any]] = []

    def start(self) -> None:
        """Start monitoring subsystem and publish MonitoringStarted event."""
        with self._lock:
            if not self._is_running:
                self._is_running = True
                evt = MonitoringStarted()
                if self._event_bus:
                    self._event_bus.publish(evt)
                logger.info("MonitoringManager STARTED.")

    def stop(self) -> None:
        """Stop monitoring subsystem and publish MonitoringStopped event."""
        with self._lock:
            if self._is_running:
                self._is_running = False
                evt = MonitoringStopped()
                if self._event_bus:
                    self._event_bus.publish(evt)
                logger.info("MonitoringManager STOPPED.")

    def is_running(self) -> bool:
        """Get monitoring active running status."""
        with self._lock:
            return self._is_running

    def register_service(
        self,
        service_name: str,
        service_type: str = "generic",
        metadata: Optional[Dict[str, str]] = None,
    ) -> ServiceRegistration:
        """Register a service with system monitor."""
        with self._lock:
            return self._system_monitor.register_service(service_name, service_type, metadata)

    def unregister_service(self, service_name: str) -> bool:
        """Unregister a service."""
        with self._lock:
            return self._system_monitor.unregister_service(service_name)

    def update_service_health(
        self,
        service_name: str,
        new_status: ServiceHealthStatus,
        latency_ms: float = 0.0,
    ) -> Optional[HealthTransitionRecord]:
        """Update service health status, record history, and notify on transitions."""
        with self._lock:
            transition = self._system_monitor.update_health_status(service_name, new_status, latency_ms)
            self._trend_analyzer.record_latency_sample(latency_ms)

            if transition:
                self._history.add_health_change(transition)

                # Send notifications on failure or recovery
                if new_status in (ServiceHealthStatus.UNHEALTHY, ServiceHealthStatus.DEGRADED):
                    n = self._notification_mgr.notify_service_failure(service_name, f"Status changed to {new_status.value}")
                    self._history.add_notification(n)
                    self._publish_notification_event(n)
                    self.trigger_alert("SERVICE_FAILURE", "ERROR", f"Service {service_name} status {new_status.value}", service_name)
                elif new_status == ServiceHealthStatus.HEALTHY:
                    n = self._notification_mgr.notify_service_recovery(service_name)
                    self._history.add_notification(n)
                    self._publish_notification_event(n)

            return transition

    def trigger_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        service_name: str = "system",
    ) -> AlertGenerated:
        """Trigger an operational alert, record to history, and publish AlertGenerated event."""
        with self._lock:
            evt = AlertGenerated(
                alert_type=alert_type,
                severity=severity,
                message=message,
                service_name=service_name,
            )
            alert_dict = evt.model_dump()
            self._active_alerts.append(alert_dict)
            self._history.add_alert(alert_dict)
            self._trend_analyzer.record_alert_event(evt.timestamp)

            if self._event_bus:
                self._event_bus.publish(evt)

            logger.warning("AlertGenerated [%s/%s]: %s", severity, alert_type, message)
            return evt

    def check_resources(self) -> ResourceSnapshot:
        """Measure current system resources and generate alert/event if thresholds breached."""
        with self._lock:
            services = self._system_monitor.get_registered_services()
            snapshot = self._resource_monitor.measure_resources(service_count=len(services))

            self._trend_analyzer.record_cpu_sample(snapshot.cpu_percent)
            self._trend_analyzer.record_memory_sample(snapshot.memory_mb)
            self._history.add_metric_snapshot(snapshot.model_dump())

            exceeded, reason = self._resource_monitor.is_threshold_exceeded(snapshot)
            if exceeded and reason:
                res_type = "CPU" if "CPU" in reason else "Memory"
                thresh = self._resource_monitor._cpu_threshold if res_type == "CPU" else self._resource_monitor._memory_threshold
                val = snapshot.cpu_percent if res_type == "CPU" else snapshot.memory_mb

                thresh_evt = ResourceThresholdExceeded(
                    resource_type=res_type,
                    value=val,
                    threshold=thresh,
                    message=reason,
                )
                if self._event_bus:
                    self._event_bus.publish(thresh_evt)

                self.trigger_alert("RESOURCE_EXCEEDED", "WARNING", reason)

            return snapshot

    def render_dashboard(self) -> DashboardSnapshot:
        """Render current DashboardSnapshot and emit DashboardUpdated event."""
        with self._lock:
            uptime = self._system_monitor.get_controller_uptime_seconds()
            state = self._system_monitor.get_controller_state()
            services = self._system_monitor.get_registered_services()
            health_summary = self._system_monitor.get_health_summary()
            failed_count = len(self._system_monitor.get_failed_services())

            res_snapshot = self._resource_monitor.measure_resources(service_count=len(services))
            trend_snapshot = self._trend_analyzer.analyze_trends(
                uptime_seconds=uptime,
                total_services=len(services),
                failed_services_count=failed_count,
            )

            dashboard = self._dashboard_renderer.render_dashboard(
                controller_state=state,
                uptime_seconds=uptime,
                services=services,
                health_summary=health_summary,
                active_alerts=list(self._active_alerts),
                resource_usage=res_snapshot,
                trend_analysis=trend_snapshot,
            )

            if self._event_bus:
                self._event_bus.publish(DashboardUpdated(snapshot=dashboard))

            return dashboard

    def generate_report(self) -> SystemStatusReport:
        """Generate an immutable SystemStatusReport."""
        with self._lock:
            uptime = self._system_monitor.get_controller_uptime_seconds()
            state = self._system_monitor.get_controller_state()
            services = self._system_monitor.get_registered_services()
            health_summary = self._system_monitor.get_health_summary()
            failed = self._system_monitor.get_failed_services()

            res_snapshot = self._resource_monitor.measure_resources(service_count=len(services))
            trend_snapshot = self._trend_analyzer.analyze_trends(
                uptime_seconds=uptime,
                total_services=len(services),
                failed_services_count=len(failed),
            )

            return ReportGenerator.build_report(
                controller_state=state,
                uptime_seconds=uptime,
                services=services,
                health_summary=health_summary,
                failed_services=failed,
                resource_usage=res_snapshot,
                trend_analysis=trend_snapshot,
                recent_alerts=list(self._active_alerts),
            )

    def _publish_notification_event(self, n) -> None:
        """Publish NotificationSent event to event bus."""
        if self._event_bus:
            self._event_bus.publish(
                NotificationSent(
                    category=n.category.value,
                    title=n.title,
                    message=n.message,
                    target_service=n.target_service,
                )
            )

    @property
    def system_monitor(self) -> SystemMonitor:
        """Get system monitor component."""
        return self._system_monitor

    @property
    def resource_monitor(self) -> ResourceMonitor:
        """Get resource monitor component."""
        return self._resource_monitor

    @property
    def log_monitor(self) -> LogMonitor:
        """Get log monitor component."""
        return self._log_monitor

    @property
    def notification_manager(self) -> NotificationManager:
        """Get notification manager component."""
        return self._notification_mgr

    @property
    def trend_analyzer(self) -> TrendAnalyzer:
        """Get trend analyzer component."""
        return self._trend_analyzer

    @property
    def history(self) -> BoundedHistory:
        """Get bounded history component."""
        return self._history
