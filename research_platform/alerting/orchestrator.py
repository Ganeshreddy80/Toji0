"""R54 Alert Orchestrator — coordinates rule evaluation and dispatch."""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from research_platform.alerting.models import Alert, AlertSeverity, AlertChannel
from research_platform.alerting.rule_engine import AlertRuleEngine
from research_platform.alerting.dispatcher import AlertDispatcher
from research_platform.alerting.repository import AlertRepository

logger = logging.getLogger(__name__)


class AlertOrchestrator:
    """Top-level coordinator for R54 Alerting Framework."""

    def __init__(
        self,
        repository: Optional[AlertRepository] = None,
        webhook_url: str = "",
    ) -> None:
        self._repository = repository or AlertRepository()
        self._rule_engine = AlertRuleEngine()
        self._dispatcher = AlertDispatcher(self._repository, webhook_url=webhook_url)

    def fire(self, alert: Alert) -> None:
        """Manually fire a pre-built alert."""
        self._dispatcher.dispatch(alert)

    def fire_simple(
        self,
        title: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.MEDIUM,
        source: str = "TOJI",
        channels: Optional[List[AlertChannel]] = None,
    ) -> Alert:
        """Convenience method to fire an alert by fields."""
        channels = channels or [AlertChannel.LOG]
        alert = Alert(title=title, message=message, severity=severity,
                      source=source, channels=channels)
        self._dispatcher.dispatch(alert)
        return alert

    def evaluate_context(self, context: Dict[str, Any]) -> List[Alert]:
        """Evaluate all rules against the context and dispatch any fired alerts."""
        fired = self._rule_engine.evaluate(context)
        for alert in fired:
            self._dispatcher.dispatch(alert)
        return fired

    def acknowledge(self, alert_id: str) -> bool:
        return self._repository.acknowledge(alert_id)

    def get_recent(self, limit: int = 50) -> List[Alert]:
        return self._repository.get_recent(limit)

    def get_unacknowledged(self) -> List[Alert]:
        return self._repository.get_unacknowledged()
