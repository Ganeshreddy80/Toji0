"""R54 Alert channels — concrete notification dispatchers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from research_platform.alerting.models import Alert, AlertChannel, NotificationResult

logger = logging.getLogger(__name__)


class LogChannel:
    """Sends alerts to the Python logging system."""

    def send(self, alert: Alert) -> NotificationResult:
        level_map = {
            "CRITICAL": logging.CRITICAL,
            "HIGH": logging.ERROR,
            "MEDIUM": logging.WARNING,
            "LOW": logging.INFO,
            "INFO": logging.DEBUG,
        }
        lvl = level_map.get(alert.severity.value, logging.INFO)
        logger.log(lvl, "[ALERT][%s][%s] %s — %s", alert.severity.value, alert.source, alert.title, alert.message)
        return NotificationResult(alert_id=alert.alert_id, channel=AlertChannel.LOG, success=True)


class ConsoleChannel:
    """Sends alerts to stdout."""

    def send(self, alert: Alert) -> NotificationResult:
        print(f"[{alert.severity.value}] {alert.title}: {alert.message}")
        return NotificationResult(alert_id=alert.alert_id, channel=AlertChannel.CONSOLE, success=True)


class DatabaseChannel:
    """Persists alerts to the database via ServiceRegistry."""

    def send(self, alert: Alert) -> NotificationResult:
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            from research_platform.persistence.repositories.configuration_repository import PostgresConfigurationRepository
            from research_platform.configuration.models import ConfigurationEntry
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            registry = ServiceRegistry()
            db = registry.get_service("Database")
            if db:
                sm = DatabaseSessionManager(db)
                repo = PostgresConfigurationRepository(sm)
                repo.save_config(ConfigurationEntry(key=f"alert:{alert.alert_id}", value=alert.model_dump()))
                return NotificationResult(alert_id=alert.alert_id, channel=AlertChannel.DATABASE, success=True)
        except Exception as e:
            logger.debug("DatabaseChannel persistence skipped: %s", e)
        return NotificationResult(alert_id=alert.alert_id, channel=AlertChannel.DATABASE,
                                  success=False, error="DB unavailable")


class WebhookChannel:
    """Sends alerts to a configured HTTP webhook URL (fire-and-forget)."""

    def __init__(self, url: str = "", timeout_sec: float = 5.0) -> None:
        self.url = url
        self.timeout_sec = timeout_sec

    def send(self, alert: Alert) -> NotificationResult:
        if not self.url:
            return NotificationResult(alert_id=alert.alert_id, channel=AlertChannel.WEBHOOK,
                                      success=False, error="No webhook URL configured")
        try:
            import urllib.request
            import json
            payload = json.dumps(alert.model_dump(), default=str).encode("utf-8")
            req = urllib.request.Request(self.url, data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout_sec):
                pass
            return NotificationResult(alert_id=alert.alert_id, channel=AlertChannel.WEBHOOK, success=True)
        except Exception as e:
            logger.warning("WebhookChannel send failed: %s", e)
            return NotificationResult(alert_id=alert.alert_id, channel=AlertChannel.WEBHOOK,
                                      success=False, error=str(e))


class TelegramChannel:
    """Sends alerts to Telegram channel via HTTP API."""

    def __init__(self, bot_token: str = "", chat_id: str = "") -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, alert: Alert) -> NotificationResult:
        if not self.bot_token or not self.chat_id:
            return NotificationResult(alert_id=alert.alert_id, channel=AlertChannel.TELEGRAM,
                                      success=False, error="Telegram credentials not configured")
        try:
            import urllib.request
            import json
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = json.dumps({
                "chat_id": self.chat_id,
                "text": f"[{alert.severity.value}] {alert.title}\n{alert.message}"
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=5.0):
                pass
            return NotificationResult(alert_id=alert.alert_id, channel=AlertChannel.TELEGRAM, success=True)
        except Exception as e:
            logger.warning("TelegramChannel send failed: %s", e)
            return NotificationResult(alert_id=alert.alert_id, channel=AlertChannel.TELEGRAM,
                                      success=False, error=str(e))
