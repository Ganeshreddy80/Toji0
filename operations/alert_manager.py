"""Thread-safe Alert Manager evaluating rules and managing alert lifecycles (Sprint 12C)."""

from __future__ import annotations

import collections
import logging
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from operations.alert_rules import AlertRule, AlertSeverity, ComparisonOperator
from operations.metrics_collector import MetricSnapshot
from operations.metrics_repository import MetricsRepository

logger = logging.getLogger(__name__)


class AlertStatus(str, Enum):
    """Lifecycle states of an operational alert."""

    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AlertRecord(BaseModel):
    """Immutable record of a triggered operational alert."""

    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str = Field(..., description="ID of triggered rule.")
    rule_name: str = Field(..., description="Name of triggered rule.")
    metric_name: str = Field(..., description="Metric name.")
    current_value: float = Field(..., description="Value that triggered alert.")
    threshold_value: float = Field(..., description="Configured rule threshold.")
    severity: AlertSeverity = Field(default=AlertSeverity.WARNING)
    status: AlertStatus = Field(default=AlertStatus.ACTIVE)
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = Field(default=None)
    resolved_at: Optional[datetime] = Field(default=None)
    acknowledged_by: Optional[str] = Field(default=None)
    resolution_note: Optional[str] = Field(default=None)
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class AlertManager:
    """Thread-safe Alert Manager tracking rules, triggering alerts, and managing lifecycle states."""

    def __init__(self, max_alerts: int = 2000) -> None:
        self._lock = threading.RLock()
        self._max_alerts = max_alerts
        # rule_id -> AlertRule
        self._rules: Dict[str, AlertRule] = {}
        # alert_id -> AlertRecord
        self._alerts: Dict[str, AlertRecord] = {}

    def register_rule(
        self,
        rule_name: str,
        metric_name: str,
        comparison_operator: ComparisonOperator = ComparisonOperator.GT,
        threshold_value: float = 80.0,
        severity: AlertSeverity = AlertSeverity.WARNING,
        description: str = "",
    ) -> AlertRule:
        """Register an operational alert rule."""
        with self._lock:
            rule = AlertRule(
                rule_name=rule_name,
                metric_name=metric_name,
                comparison_operator=comparison_operator,
                threshold_value=threshold_value,
                severity=severity,
                description=description,
            )
            self._rules[rule.rule_id] = rule
            logger.info("Registered alert rule '%s' (%s %s %f)", rule_name, metric_name, comparison_operator.value, threshold_value)
            return rule

    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get rule specification by ID."""
        with self._lock:
            return self._rules.get(rule_id)

    def list_rules(self) -> List[AlertRule]:
        """List all registered alert rules."""
        with self._lock:
            return list(self._rules.values())

    def evaluate_snapshot(self, snapshot: MetricSnapshot) -> List[AlertRecord]:
        """Evaluate a single metric snapshot against all active rules for that metric."""
        triggered: List[AlertRecord] = []
        with self._lock:
            for rule in self._rules.values():
                if rule.enabled and rule.metric_name == snapshot.metric_name:
                    if rule.evaluate_value(snapshot.value):
                        # Enforce capacity
                        if len(self._alerts) >= self._max_alerts:
                            oldest_id = next(iter(self._alerts))
                            del self._alerts[oldest_id]

                        alert = AlertRecord(
                            rule_id=rule.rule_id,
                            rule_name=rule.rule_name,
                            metric_name=rule.metric_name,
                            current_value=snapshot.value,
                            threshold_value=rule.threshold_value,
                            severity=rule.severity,
                            status=AlertStatus.ACTIVE,
                        )
                        self._alerts[alert.alert_id] = alert
                        triggered.append(alert)
                        logger.warning("Alert triggered: [%s] '%s' (%f %s %f)", rule.severity.value, rule.rule_name, snapshot.value, rule.comparison_operator.value, rule.threshold_value)
        return triggered

    def evaluate_metrics(self, repo: MetricsRepository) -> List[AlertRecord]:
        """Evaluate all active rules against latest snapshots in metrics repository."""
        newly_triggered: List[AlertRecord] = []
        with self._lock:
            for rule in self._rules.values():
                if not rule.enabled:
                    continue
                snapshots = repo.get_snapshots(metric_name=rule.metric_name)
                if snapshots:
                    latest = snapshots[-1]
                    if rule.evaluate_value(latest.value):
                        if len(self._alerts) >= self._max_alerts:
                            oldest_id = next(iter(self._alerts))
                            del self._alerts[oldest_id]

                        alert = AlertRecord(
                            rule_id=rule.rule_id,
                            rule_name=rule.rule_name,
                            metric_name=rule.metric_name,
                            current_value=latest.value,
                            threshold_value=rule.threshold_value,
                            severity=rule.severity,
                            status=AlertStatus.ACTIVE,
                        )
                        self._alerts[alert.alert_id] = alert
                        newly_triggered.append(alert)
        return newly_triggered

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "operator") -> AlertRecord:
        """Acknowledge an active alert."""
        with self._lock:
            alert = self._get_alert_or_raise(alert_id)
            if alert.status == AlertStatus.RESOLVED:
                return alert

            updated = AlertRecord(
                alert_id=alert.alert_id,
                rule_id=alert.rule_id,
                rule_name=alert.rule_name,
                metric_name=alert.metric_name,
                current_value=alert.current_value,
                threshold_value=alert.threshold_value,
                severity=alert.severity,
                status=AlertStatus.ACKNOWLEDGED,
                triggered_at=alert.triggered_at,
                acknowledged_at=datetime.now(timezone.utc),
                acknowledged_by=acknowledged_by,
            )
            self._alerts[alert_id] = updated
            logger.info("Acknowledged alert '%s' by '%s'", alert_id, acknowledged_by)
            return updated

    def resolve_alert(self, alert_id: str, resolution_note: str = "Condition normalized") -> AlertRecord:
        """Resolve an active or acknowledged alert."""
        with self._lock:
            alert = self._get_alert_or_raise(alert_id)
            if alert.status == AlertStatus.RESOLVED:
                return alert

            updated = AlertRecord(
                alert_id=alert.alert_id,
                rule_id=alert.rule_id,
                rule_name=alert.rule_name,
                metric_name=alert.metric_name,
                current_value=alert.current_value,
                threshold_value=alert.threshold_value,
                severity=alert.severity,
                status=AlertStatus.RESOLVED,
                triggered_at=alert.triggered_at,
                acknowledged_at=alert.acknowledged_at,
                acknowledged_by=alert.acknowledged_by,
                resolved_at=datetime.now(timezone.utc),
                resolution_note=resolution_note,
            )
            self._alerts[alert_id] = updated
            logger.info("Resolved alert '%s': %s", alert_id, resolution_note)
            return updated

    def get_active_alerts(self) -> List[AlertRecord]:
        """Retrieve all currently active or acknowledged alerts."""
        with self._lock:
            return [a for a in self._alerts.values() if a.status in (AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED)]

    def get_alert_history(self) -> List[AlertRecord]:
        """Retrieve full alert history."""
        with self._lock:
            return list(self._alerts.values())

    def _get_alert_or_raise(self, alert_id: str) -> AlertRecord:
        alert = self._alerts.get(alert_id)
        if not alert:
            raise KeyError(f"Alert '{alert_id}' not found")
        return alert

    def count(self) -> int:
        """Return total count of recorded alerts."""
        with self._lock:
            return len(self._alerts)

    def clear(self) -> None:
        """Clear all rules and alert records."""
        with self._lock:
            self._rules.clear()
            self._alerts.clear()
