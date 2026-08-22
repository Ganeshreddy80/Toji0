"""R54 Alert Dispatcher — routes alerts to configured channels."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from research_platform.alerting.models import Alert, AlertChannel, AlertStatus, NotificationResult
from research_platform.alerting.channels import LogChannel, ConsoleChannel, DatabaseChannel, WebhookChannel, TelegramChannel
from research_platform.alerting.repository import AlertRepository

import os

logger = logging.getLogger(__name__)


class AlertDispatcher:
    """Dispatches alerts through registered channels and persists results."""

    def __init__(self, repository: AlertRepository, webhook_url: str = "") -> None:
        self._repository = repository
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self._channels: Dict[AlertChannel, Any] = {
            AlertChannel.LOG: LogChannel(),
            AlertChannel.CONSOLE: ConsoleChannel(),
            AlertChannel.DATABASE: DatabaseChannel(),
            AlertChannel.WEBHOOK: WebhookChannel(url=webhook_url),
            AlertChannel.TELEGRAM: TelegramChannel(bot_token=bot_token, chat_id=chat_id),
        }

    def dispatch(self, alert: Alert) -> List[NotificationResult]:
        results: List[NotificationResult] = []
        all_success = True

        for channel in alert.channels:
            dispatcher = self._channels.get(channel)
            if dispatcher:
                try:
                    result = dispatcher.send(alert)
                    results.append(result)
                    if not result.success:
                        all_success = False
                except Exception as e:
                    logger.error("Channel %s dispatch error: %s", channel.value, e)
                    results.append(NotificationResult(alert_id=alert.alert_id, channel=channel,
                                                      success=False, error=str(e)))
                    all_success = False

        alert.status = AlertStatus.SENT if all_success else AlertStatus.FAILED
        alert.sent_at = datetime.now(timezone.utc)
        self._repository.save(alert)
        self._publish_event(alert)
        return results

    def _publish_event(self, alert: Alert) -> None:
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            from research_platform.alerting.events import AlertFired
            eb = ServiceRegistry().get_service("EventBus")
            if eb:
                ev = AlertFired(alert_id=alert.alert_id, title=alert.title,
                                severity=alert.severity.value, source=alert.source)
                eb.publish("AlertFired", ev.model_dump())
        except Exception:
            pass
