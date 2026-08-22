"""R54 Alert Rule Engine — evaluates conditions and fires alerts."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from research_platform.alerting.models import Alert, AlertRule, AlertSeverity, AlertChannel

logger = logging.getLogger(__name__)


class AlertRuleEngine:
    """Evaluates registered alert rules against platform metrics context."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rules: List[AlertRule] = []
        self._handlers: Dict[str, Callable[[AlertRule, Dict[str, Any]], bool]] = {}

        # Register built-in rules
        self._register_builtin_rules()

    def add_rule(self, rule: AlertRule, handler: Optional[Callable] = None) -> None:
        with self._lock:
            self._rules.append(rule)
            if handler:
                self._handlers[rule.rule_id] = handler

    def evaluate(self, context: Dict[str, Any]) -> List[Alert]:
        """Evaluate all enabled rules against the provided context, return triggered alerts."""
        fired: List[Alert] = []
        now = datetime.now(timezone.utc)

        with self._lock:
            for rule in self._rules:
                if not rule.enabled:
                    continue
                # Respect cooldown
                if rule.last_fired_at:
                    elapsed = (now - rule.last_fired_at).total_seconds()
                    if elapsed < rule.cooldown_sec:
                        continue
                # Evaluate
                try:
                    handler = self._handlers.get(rule.rule_id)
                    triggered = handler(rule, context) if handler else False
                    if triggered:
                        rule.fire_count += 1
                        rule.last_fired_at = now
                        alert = Alert(
                            title=rule.name,
                            message=f"Alert rule '{rule.name}' triggered. Context keys: {list(context.keys())}",
                            severity=rule.severity,
                            source="AlertRuleEngine",
                            category=rule.description or "RULE",
                            channels=rule.channels,
                        )
                        fired.append(alert)
                except Exception as e:
                    logger.error("Rule '%s' evaluation error: %s", rule.name, e)

        return fired

    def _register_builtin_rules(self) -> None:
        """Register standard platform alert rules."""
        # Validation certification failure
        rule_cert = AlertRule(
            name="ValidationCertificationFailed",
            description="VALIDATION",
            severity=AlertSeverity.HIGH,
            channels=[AlertChannel.LOG],
            cooldown_sec=600.0,
        )
        self.add_rule(rule_cert, handler=lambda r, ctx: not ctx.get("certified", True))

        # High CPU usage
        rule_cpu = AlertRule(
            name="HighCPUUsage",
            description="PERFORMANCE",
            severity=AlertSeverity.MEDIUM,
            channels=[AlertChannel.LOG],
            cooldown_sec=300.0,
        )
        self.add_rule(rule_cpu, handler=lambda r, ctx: ctx.get("cpu_pct", 0.0) > 85.0)

        # Low disk space
        rule_disk = AlertRule(
            name="LowDiskSpace",
            description="RESOURCE",
            severity=AlertSeverity.HIGH,
            channels=[AlertChannel.LOG],
            cooldown_sec=1800.0,
        )
        self.add_rule(rule_disk, handler=lambda r, ctx: ctx.get("free_disk_gb", 999.0) < 1.0)

        # Drawdown threshold breached
        rule_dd = AlertRule(
            name="DrawdownThresholdBreached",
            description="RISK",
            severity=AlertSeverity.CRITICAL,
            channels=[AlertChannel.LOG, AlertChannel.CONSOLE],
            cooldown_sec=3600.0,
        )
        self.add_rule(rule_dd, handler=lambda r, ctx: ctx.get("drawdown_pct", 0.0) > 0.08)
