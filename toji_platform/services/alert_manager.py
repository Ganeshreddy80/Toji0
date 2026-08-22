"""Alert Manager implementation for Toji platform."""

from __future__ import annotations

import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AlertLevel(enum.Enum):
    """Alert severity levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Alert:
    """Represents a generated health alert."""

    def __init__(
        self,
        rule_name: str,
        level: AlertLevel,
        message: str,
        value: Any,
        timestamp: Optional[datetime] = None,
    ) -> None:
        self.rule_name = rule_name
        self.level = level
        self.message = message
        self.value = value
        self.timestamp = timestamp or datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert alert object to JSON-compatible dictionary."""
        return {
            "rule_name": self.rule_name,
            "level": self.level.value,
            "message": self.message,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
        }


class AlertManager:
    """Evaluates metrics from RuntimeHealthMonitor against threshold rules and compiles alerts."""

    def __init__(self, health_monitor: Any, config: Optional[dict[str, Any]] = None) -> None:
        self._monitor = health_monitor
        self._rules_config = {
            "memory_warning_mb": 500.0,
            "memory_error_mb": 800.0,
            "memory_critical_mb": 1000.0,
            "cpu_warning_percent": 80.0,
            "cpu_error_percent": 90.0,
            "cpu_critical_percent": 95.0,
            "heartbeat_error_seconds": 5.0,
            "heartbeat_critical_seconds": 10.0,
            "exceptions_warning": 1,
            "exceptions_error": 5,
            "exceptions_critical": 10,
            "restarts_warning": 1,
            "restarts_error": 3,
            "restarts_critical": 5,
            "threads_warning": 50,
            "threads_error": 80,
            "threads_critical": 100,
        }
        if config:
            self._rules_config.update(config)
        self._alerts: list[Alert] = []
        self._lock = threading.Lock()

    def evaluate_rules(self) -> list[Alert]:
        """Query metrics from RuntimeHealthMonitor, evaluate thresholds, and compile active alerts."""
        report = self._monitor.get_health_report()
        new_alerts = []

        # 1. Memory usage threshold
        mem = report.get("memory_usage_mb", 0.0)
        if mem > self._rules_config["memory_critical_mb"]:
            new_alerts.append(Alert("memory_usage", AlertLevel.CRITICAL, f"Memory usage CRITICAL: {mem}MB exceeds threshold", mem))
        elif mem > self._rules_config["memory_error_mb"]:
            new_alerts.append(Alert("memory_usage", AlertLevel.ERROR, f"Memory usage ERROR: {mem}MB exceeds threshold", mem))
        elif mem > self._rules_config["memory_warning_mb"]:
            new_alerts.append(Alert("memory_usage", AlertLevel.WARNING, f"Memory usage WARNING: {mem}MB exceeds threshold", mem))

        # 2. CPU usage threshold
        cpu = report.get("cpu_usage_percent", 0.0)
        if cpu > self._rules_config["cpu_critical_percent"]:
            new_alerts.append(Alert("cpu_usage", AlertLevel.CRITICAL, f"CPU usage CRITICAL: {cpu}% exceeds threshold", cpu))
        elif cpu > self._rules_config["cpu_error_percent"]:
            new_alerts.append(Alert("cpu_usage", AlertLevel.ERROR, f"CPU usage ERROR: {cpu}% exceeds threshold", cpu))
        elif cpu > self._rules_config["cpu_warning_percent"]:
            new_alerts.append(Alert("cpu_usage", AlertLevel.WARNING, f"CPU usage WARNING: {cpu}% exceeds threshold", cpu))

        # 3. Heartbeat timeout
        hb_status = report.get("heartbeat_status", {})
        last_hb_str = hb_status.get("last_heartbeat")
        if last_hb_str:
            try:
                last_hb = datetime.fromisoformat(last_hb_str)
                elapsed = (datetime.now(timezone.utc) - last_hb).total_seconds()
                if elapsed > self._rules_config["heartbeat_critical_seconds"]:
                    new_alerts.append(Alert("heartbeat_timeout", AlertLevel.CRITICAL, f"Heartbeat missed for {elapsed:.1f}s", elapsed))
                elif elapsed > self._rules_config["heartbeat_error_seconds"]:
                    new_alerts.append(Alert("heartbeat_timeout", AlertLevel.ERROR, f"Heartbeat missed for {elapsed:.1f}s", elapsed))
            except Exception:
                new_alerts.append(Alert("heartbeat_timeout", AlertLevel.WARNING, "Heartbeat timestamp parsing failed", last_hb_str))
        else:
            # Heartbeat never received
            new_alerts.append(Alert("heartbeat_timeout", AlertLevel.WARNING, "Heartbeat never received", None))

        # 4. Exception count threshold
        exceptions = report.get("exception_count", 0)
        if exceptions >= self._rules_config["exceptions_critical"]:
            new_alerts.append(Alert("exception_rate", AlertLevel.CRITICAL, f"Exceptions CRITICAL: {exceptions} total exceptions", exceptions))
        elif exceptions >= self._rules_config["exceptions_error"]:
            new_alerts.append(Alert("exception_rate", AlertLevel.ERROR, f"Exceptions ERROR: {exceptions} total exceptions", exceptions))
        elif exceptions >= self._rules_config["exceptions_warning"]:
            new_alerts.append(Alert("exception_rate", AlertLevel.WARNING, f"Exceptions WARNING: {exceptions} total exceptions", exceptions))

        # 5. Restart frequency
        restarts = report.get("restart_count", 0)
        if restarts >= self._rules_config["restarts_critical"]:
            new_alerts.append(Alert("restart_frequency", AlertLevel.CRITICAL, f"Restart count CRITICAL: {restarts} restarts", restarts))
        elif restarts >= self._rules_config["restarts_error"]:
            new_alerts.append(Alert("restart_frequency", AlertLevel.ERROR, f"Restart count ERROR: {restarts} restarts", restarts))
        elif restarts >= self._rules_config["restarts_warning"]:
            new_alerts.append(Alert("restart_frequency", AlertLevel.WARNING, f"Restart count WARNING: {restarts} restarts", restarts))

        # 6. Thread count growth
        threads = report.get("active_thread_count", 0)
        if threads >= self._rules_config["threads_critical"]:
            new_alerts.append(Alert("thread_count", AlertLevel.CRITICAL, f"Thread count CRITICAL: {threads} active threads", threads))
        elif threads >= self._rules_config["threads_error"]:
            new_alerts.append(Alert("thread_count", AlertLevel.ERROR, f"Thread count ERROR: {threads} active threads", threads))
        elif threads >= self._rules_config["threads_warning"]:
            new_alerts.append(Alert("thread_count", AlertLevel.WARNING, f"Thread count WARNING: {threads} active threads", threads))

        # 7. Plugin failures
        plugins = report.get("plugin_states", {})
        failed_plugins = [p_id for p_id, p_state in plugins.items() if p_state == "failed"]
        if failed_plugins:
            new_alerts.append(Alert("plugin_failure", AlertLevel.CRITICAL, f"Plugin failures detected: {', '.join(failed_plugins)}", failed_plugins))

        # 8. Lifecycle failures
        lifecycles = report.get("lifecycle_status", {})
        failed_lifecycles = [c_name for c_name, c_state in lifecycles.items() if c_state == "stopped"]
        # Skip alert if kernel itself is stopped (which is valid and normal)
        k_state = report.get("kernel_state")
        if k_state == "running" and failed_lifecycles:
            new_alerts.append(Alert("lifecycle_failure", AlertLevel.ERROR, f"Lifecycle components stopped: {', '.join(failed_lifecycles)}", failed_lifecycles))

        # 9. Event bus failures
        eb_health = report.get("event_bus_health", {})
        eb_failures = eb_health.get("publish_failures", 0)
        if eb_failures > 0:
            new_alerts.append(Alert("event_bus_failure", AlertLevel.ERROR, f"Event bus publish failures: {eb_failures}", eb_failures))

        # 10. Unknown kernel state
        if k_state not in ("running", "stopped", "booting", "shutting_down"):
            new_alerts.append(Alert("kernel_state", AlertLevel.CRITICAL, f"Kernel state invalid or unknown: {k_state}", k_state))
        elif k_state == "failed":
            new_alerts.append(Alert("kernel_state", AlertLevel.CRITICAL, "Kernel execution in FAILED state", k_state))

        with self._lock:
            self._alerts = new_alerts
        return new_alerts

    def get_active_alerts(self) -> list[Alert]:
        """Retrieve the compiled list of active alerts."""
        with self._lock:
            return list(self._alerts)
