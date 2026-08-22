"""Thread-safe Operational Automation Manager & Event Orchestrator for Mission Control (Sprint 10C)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from mission_control.audit_log import AuditLog, AuditLogEntry
from mission_control.automation_metrics import AutomationMetricsCollector, AutomationMetricsSnapshot
from mission_control.dependency_manager import DependencyManager
from mission_control.escalation_manager import EscalationLevel, EscalationManager, EscalationReason, EscalationRecord
from mission_control.maintenance_scheduler import MaintenanceScheduler, MaintenanceWindow
from mission_control.policies import AutoRestartPolicy, EscalationPolicy, MaintenancePolicy, RecoveryPolicy
from mission_control.recovery_engine import RecoveryAttemptRecord, RecoveryEngine, RecoveryType
from mission_control.restart_manager import RestartManager, RestartRecord
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Standard Automation Events (Immutable Pydantic V2 Models)
# -------------------------------------------------------------------------

class AutomationEnabled(BaseModel):
    """Event emitted when operational automation is enabled."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="AutomationEnabled")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class AutomationDisabled(BaseModel):
    """Event emitted when operational automation is disabled."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="AutomationDisabled")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class RecoveryStarted(BaseModel):
    """Event emitted when automated service recovery is initiated."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="RecoveryStarted")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service_name: str = Field(..., description="Target service name.")
    recovery_type: str = Field(..., description="Recovery classification type.")
    reason: str = Field(..., description="Recovery trigger reason.")

    model_config = ConfigDict(frozen=True)


class RecoveryCompleted(BaseModel):
    """Event emitted when automated service recovery completes."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="RecoveryCompleted")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service_name: str = Field(..., description="Target service name.")
    success: bool = Field(..., description="Recovery execution success flag.")
    attempt_number: int = Field(..., ge=1, description="Recovery attempt count.")
    message: str = Field(..., description="Recovery result message.")

    model_config = ConfigDict(frozen=True)


class RestartPerformed(BaseModel):
    """Event emitted when a service restart is executed."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="RestartPerformed")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service_name: str = Field(..., description="Target service name.")
    is_manual: bool = Field(default=False, description="Manual or automatic flag.")
    operator: str = Field(default="SYSTEM", description="Requesting operator.")
    reason: str = Field(..., description="Restart reason.")

    model_config = ConfigDict(frozen=True)


class MaintenanceStarted(BaseModel):
    """Event emitted when a maintenance window becomes active."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="MaintenanceStarted")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    window_id: str = Field(..., description="Maintenance window UUID.")
    service_name: str = Field(..., description="Target service name.")
    description: str = Field(..., description="Maintenance description.")

    model_config = ConfigDict(frozen=True)


class MaintenanceEnded(BaseModel):
    """Event emitted when a maintenance window completes or terminates."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="MaintenanceEnded")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    window_id: str = Field(..., description="Maintenance window UUID.")
    service_name: str = Field(..., description="Target service name.")

    model_config = ConfigDict(frozen=True)


class DependencyFailure(BaseModel):
    """Event emitted when upstream service dependency failure impacts downstream services."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="DependencyFailure")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    failed_service: str = Field(..., description="Failed upstream service name.")
    impacted_services: List[str] = Field(default_factory=list, description="Downstream impacted services.")

    model_config = ConfigDict(frozen=True)


class EscalationRaised(BaseModel):
    """Event emitted when an operational escalation is raised."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="EscalationRaised")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service_name: str = Field(..., description="Target service name.")
    level: str = Field(..., description="Escalation level.")
    reason: str = Field(..., description="Escalation reason.")
    message: str = Field(..., description="Escalation summary.")

    model_config = ConfigDict(frozen=True)


# -------------------------------------------------------------------------
# Main Automation Manager Implementation
# -------------------------------------------------------------------------

class AutomationManager:
    """Thread-safe Main Automation Manager orchestrating recovery, restart, maintenance, dependency, and escalation components."""

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        recovery_engine: Optional[RecoveryEngine] = None,
        restart_manager: Optional[RestartManager] = None,
        maintenance_scheduler: Optional[MaintenanceScheduler] = None,
        dependency_manager: Optional[DependencyManager] = None,
        escalation_manager: Optional[EscalationManager] = None,
        audit_log: Optional[AuditLog] = None,
        metrics_collector: Optional[AutomationMetricsCollector] = None,
        maintenance_policy: Optional[MaintenancePolicy] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._enabled: bool = True

        self._recovery_engine = recovery_engine or RecoveryEngine()
        self._restart_manager = restart_manager or RestartManager()
        self._maintenance_scheduler = maintenance_scheduler or MaintenanceScheduler()
        self._dependency_manager = dependency_manager or DependencyManager()
        self._escalation_manager = escalation_manager or EscalationManager()
        self._audit_log = audit_log or AuditLog()
        self._metrics = metrics_collector or AutomationMetricsCollector()
        self._maintenance_policy: MaintenancePolicy = maintenance_policy or MaintenancePolicy()

    def enable(self) -> None:
        """Enable operational automation subsystem."""
        with self._lock:
            if not self._enabled:
                self._enabled = True
                evt = AutomationEnabled()
                if self._event_bus:
                    self._event_bus.publish(evt)
                self._audit_log.record("ENABLE_AUTOMATION", "SYSTEM", "SUCCESS", "Automation subsystem enabled")
                logger.info("AutomationManager ENABLED.")

    def disable(self) -> None:
        """Disable operational automation subsystem."""
        with self._lock:
            if self._enabled:
                self._enabled = False
                evt = AutomationDisabled()
                if self._event_bus:
                    self._event_bus.publish(evt)
                self._audit_log.record("DISABLE_AUTOMATION", "SYSTEM", "SUCCESS", "Automation subsystem disabled")
                logger.info("AutomationManager DISABLED.")

    def is_enabled(self) -> bool:
        """Check if automation subsystem is enabled."""
        with self._lock:
            return self._enabled

    def execute_recovery(
        self,
        service_name: str,
        failure_type: str = "SERVICE_RECOVERY",
        reason: str = "Service unhealthy",
    ) -> Tuple[bool, Optional[RecoveryAttemptRecord], str]:
        """Execute automated recovery workflow for a service."""
        with self._lock:
            if not self._enabled:
                self._audit_log.record("RECOVERY", service_name, "SKIPPED", "Automation subsystem is disabled")
                return False, None, "Automation is disabled"

            # Check maintenance window suppression — governed by MaintenancePolicy
            if self._maintenance_scheduler.is_in_maintenance(service_name):
                if not self._maintenance_policy.allow_auto_recovery_during_maintenance:
                    msg = f"Service '{service_name}' is currently in maintenance window"
                    self._audit_log.record("RECOVERY", service_name, "SKIPPED", msg)
                    return False, None, msg

            self._metrics.record_recovery_attempt()

            # Publish RecoveryStarted event
            if self._event_bus:
                self._event_bus.publish(
                    RecoveryStarted(
                        service_name=service_name,
                        recovery_type=failure_type,
                        reason=reason,
                    )
                )

            # Map failure type string to enum
            rec_enum = RecoveryType.SERVICE_RECOVERY
            if failure_type == "HEARTBEAT_RECOVERY":
                rec_enum = RecoveryType.HEARTBEAT_RECOVERY
            elif failure_type == "DEGRADED_RECOVERY":
                rec_enum = RecoveryType.DEGRADED_RECOVERY
            elif failure_type == "REPEATED_FAILURE_RECOVERY":
                rec_enum = RecoveryType.REPEATED_FAILURE_RECOVERY

            success, rec, msg = False, None, ""
            if rec_enum == RecoveryType.HEARTBEAT_RECOVERY:
                success, rec, msg = self._recovery_engine.execute_heartbeat_recovery(service_name, latency_ms=500.0)
            elif rec_enum == RecoveryType.DEGRADED_RECOVERY:
                success, rec, msg = self._recovery_engine.execute_degraded_recovery(service_name, reason)
            elif rec_enum == RecoveryType.REPEATED_FAILURE_RECOVERY:
                success, rec, msg = self._recovery_engine.execute_repeated_failure_recovery(service_name, failure_count=3)
            else:
                success, rec, msg = self._recovery_engine.execute_service_recovery(service_name, reason)

            if success and rec:
                self._metrics.record_recovery_success()
                self._audit_log.record("RECOVERY", service_name, "SUCCESS", msg)

                # Attempt restart alongside recovery
                restart_ok, r_rec, r_msg = self._restart_manager.request_restart(service_name, reason)
                if restart_ok and r_rec:
                    self._metrics.record_restart()
                    self._publish_restart_event(r_rec)

            else:
                self._metrics.record_recovery_failure()
                self._audit_log.record("RECOVERY", service_name, "FAILED", msg)

                # Escalate on recovery exhaustion
                attempts = self._recovery_engine.get_attempt_count(service_name)
                esc_record = self._escalation_manager.escalate_recovery_exhaustion(service_name, attempts)
                self._metrics.record_escalation()
                self._publish_escalation_event(esc_record)
                self._audit_log.record("ESCALATION", service_name, "ESCALATED", esc_record.message)

            # Publish RecoveryCompleted event
            if rec and self._event_bus:
                self._event_bus.publish(
                    RecoveryCompleted(
                        service_name=service_name,
                        success=success,
                        attempt_number=rec.attempt_number,
                        message=msg,
                    )
                )

            return success, rec, msg

    def execute_policy(self, policy: Any, service_name: str) -> bool:
        """Apply policy configuration update or policy-driven action for a service."""
        with self._lock:
            if isinstance(policy, AutoRestartPolicy):
                self._restart_manager.set_policy(policy)
                self._audit_log.record("POLICY_UPDATE", service_name, "SUCCESS", "AutoRestartPolicy updated")
                return True
            elif isinstance(policy, RecoveryPolicy):
                self._recovery_engine.set_policy(policy)
                self._audit_log.record("POLICY_UPDATE", service_name, "SUCCESS", "RecoveryPolicy updated")
                return True
            elif isinstance(policy, EscalationPolicy):
                self._escalation_manager.set_policy(policy)
                self._audit_log.record("POLICY_UPDATE", service_name, "SUCCESS", "EscalationPolicy updated")
                return True
            return False

    def handle_service_failure(self, service_name: str, reason: str) -> Tuple[bool, List[str]]:
        """Record dependency failure, propagate to downstream dependents, and trigger recovery."""
        with self._lock:
            impacted = self._dependency_manager.record_service_failure(service_name)

            if impacted and self._event_bus:
                self._event_bus.publish(
                    DependencyFailure(
                        failed_service=service_name,
                        impacted_services=impacted,
                    )
                )

            # Escalate dependency failure for impacted services
            for dep_svc in impacted:
                esc = self._escalation_manager.escalate_dependency_failure(dep_svc, [service_name])
                self._metrics.record_escalation()
                self._publish_escalation_event(esc)

            # Execute recovery for the failed service
            success, _, _ = self.execute_recovery(service_name, "SERVICE_RECOVERY", reason)
            return success, impacted

    def start_maintenance_window(
        self,
        service_name: str,
        start_time: datetime,
        end_time: datetime,
        description: str,
    ) -> Optional[MaintenanceWindow]:
        """Schedule and activate a maintenance window."""
        with self._lock:
            window = self._maintenance_scheduler.schedule_maintenance(service_name, start_time, end_time, description)
            active_window = self._maintenance_scheduler.start_maintenance(window.window_id)

            if active_window:
                self._metrics.record_maintenance()
                self._audit_log.record("MAINTENANCE_START", service_name, "SUCCESS", description)
                if self._event_bus:
                    self._event_bus.publish(
                        MaintenanceStarted(
                            window_id=active_window.window_id,
                            service_name=service_name,
                            description=description,
                        )
                    )

            return active_window

    def end_maintenance_window(self, window_id: str) -> Optional[MaintenanceWindow]:
        """End an active maintenance window."""
        with self._lock:
            completed = self._maintenance_scheduler.end_maintenance(window_id)
            if completed:
                self._audit_log.record("MAINTENANCE_END", completed.service_name, "SUCCESS", "Maintenance completed")
                if self._event_bus:
                    self._event_bus.publish(
                        MaintenanceEnded(
                            window_id=window_id,
                            service_name=completed.service_name,
                        )
                    )
            return completed

    def _publish_restart_event(self, record: RestartRecord) -> None:
        """Publish RestartPerformed event to event bus."""
        if self._event_bus:
            self._event_bus.publish(
                RestartPerformed(
                    service_name=record.service_name,
                    is_manual=record.is_manual,
                    operator=record.operator,
                    reason=record.reason,
                )
            )

    def _publish_escalation_event(self, record: EscalationRecord) -> None:
        """Publish EscalationRaised event to event bus."""
        if self._event_bus:
            self._event_bus.publish(
                EscalationRaised(
                    service_name=record.service_name,
                    level=record.level.value,
                    reason=record.reason.value,
                    message=record.message,
                )
            )

    @property
    def recovery_engine(self) -> RecoveryEngine:
        """Get recovery engine sub-component."""
        return self._recovery_engine

    @property
    def restart_manager(self) -> RestartManager:
        """Get restart manager sub-component."""
        return self._restart_manager

    @property
    def maintenance_scheduler(self) -> MaintenanceScheduler:
        """Get maintenance scheduler sub-component."""
        return self._maintenance_scheduler

    @property
    def dependency_manager(self) -> DependencyManager:
        """Get dependency manager sub-component."""
        return self._dependency_manager

    @property
    def escalation_manager(self) -> EscalationManager:
        """Get escalation manager sub-component."""
        return self._escalation_manager

    @property
    def audit_log(self) -> AuditLog:
        """Get audit log sub-component."""
        return self._audit_log

    @property
    def metrics(self) -> AutomationMetricsCollector:
        """Get telemetry metrics collector sub-component."""
        return self._metrics
