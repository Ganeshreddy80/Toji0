"""Mission Control Subsystem (Sprint 10B & 10C — Monitoring, Dashboard & Operational Automation)."""

from mission_control.audit_log import AuditLog, AuditLogEntry
from mission_control.automation import (
    AutomationDisabled,
    AutomationEnabled,
    AutomationManager,
    DependencyFailure,
    EscalationRaised,
    MaintenanceEnded,
    MaintenanceStarted,
    RecoveryCompleted,
    RecoveryStarted,
    RestartPerformed,
)
from mission_control.automation_metrics import (
    AutomationMetricsCollector,
    AutomationMetricsSnapshot,
)
from mission_control.dashboard_renderer import DashboardRenderer, DashboardSnapshot
from mission_control.dependency_manager import DependencyManager, DependencyNode
from mission_control.escalation_manager import (
    EscalationLevel,
    EscalationManager,
    EscalationReason,
    EscalationRecord,
)
from mission_control.history import BoundedHistory, HealthTransitionRecord
from mission_control.log_monitor import LogEntry, LogLevel, LogMonitor
from mission_control.maintenance_scheduler import (
    MaintenanceScheduler,
    MaintenanceState,
    MaintenanceWindow,
)
from mission_control.monitoring import (
    AlertGenerated,
    DashboardUpdated,
    MonitoringManager,
    MonitoringStarted,
    MonitoringStopped,
    NotificationSent,
    ResourceThresholdExceeded,
)
from mission_control.notification_manager import (
    Notification,
    NotificationCategory,
    NotificationManager,
)
from mission_control.policies import (
    AutoRestartPolicy,
    EscalationPolicy,
    MaintenancePolicy,
    RecoveryPolicy,
)
from mission_control.recovery_engine import (
    RecoveryAttemptRecord,
    RecoveryEngine,
    RecoveryType,
)
from mission_control.reports import ReportGenerator, SystemStatusReport
from mission_control.resource_monitor import ResourceMonitor, ResourceSnapshot
from mission_control.restart_manager import RestartManager, RestartRecord
from mission_control.system_monitor import (
    ServiceHealthStatus,
    ServiceRegistration,
    SystemMonitor,
)
from mission_control.trend_analyzer import TrendAnalysisSnapshot, TrendAnalyzer

__all__ = [
    # Sprint 10B
    "MonitoringManager",
    "SystemMonitor",
    "ServiceHealthStatus",
    "ServiceRegistration",
    "ResourceMonitor",
    "ResourceSnapshot",
    "LogMonitor",
    "LogLevel",
    "LogEntry",
    "NotificationManager",
    "NotificationCategory",
    "Notification",
    "TrendAnalyzer",
    "TrendAnalysisSnapshot",
    "DashboardRenderer",
    "DashboardSnapshot",
    "BoundedHistory",
    "HealthTransitionRecord",
    "ReportGenerator",
    "SystemStatusReport",
    "MonitoringStarted",
    "MonitoringStopped",
    "DashboardUpdated",
    "AlertGenerated",
    "NotificationSent",
    "ResourceThresholdExceeded",
    # Sprint 10C
    "AutomationManager",
    "RecoveryEngine",
    "RecoveryType",
    "RecoveryAttemptRecord",
    "RestartManager",
    "RestartRecord",
    "MaintenanceScheduler",
    "MaintenanceState",
    "MaintenanceWindow",
    "DependencyManager",
    "DependencyNode",
    "EscalationManager",
    "EscalationLevel",
    "EscalationReason",
    "EscalationRecord",
    "AuditLog",
    "AuditLogEntry",
    "AutomationMetricsCollector",
    "AutomationMetricsSnapshot",
    "AutoRestartPolicy",
    "RecoveryPolicy",
    "EscalationPolicy",
    "MaintenancePolicy",
    "AutomationEnabled",
    "AutomationDisabled",
    "RecoveryStarted",
    "RecoveryCompleted",
    "RestartPerformed",
    "MaintenanceStarted",
    "MaintenanceEnded",
    "DependencyFailure",
    "EscalationRaised",
]
