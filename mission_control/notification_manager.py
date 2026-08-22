"""Thread-safe In-Memory Notification Manager for Mission Control (Sprint 10B)."""

from __future__ import annotations

import collections
from datetime import datetime, timezone
from enum import Enum
import logging
import threading
import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class NotificationCategory(str, Enum):
    """Category enumeration for notifications."""

    SERVICE_FAILURE = "SERVICE_FAILURE"
    SERVICE_RECOVERY = "SERVICE_RECOVERY"
    CRITICAL_ALERT = "CRITICAL_ALERT"
    HEARTBEAT_FAILURE = "HEARTBEAT_FAILURE"
    SYSTEM_INFO = "SYSTEM_INFO"


class Notification(BaseModel):
    """Immutable Notification record model."""

    notification_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique notification UUID.",
    )
    category: NotificationCategory = Field(..., description="Notification classification category.")
    title: str = Field(..., description="Short notification summary title.")
    message: str = Field(..., description="Detailed notification text.")
    target_service: str = Field(default="system", description="Associated service identifier.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Notification creation timestamp.",
    )

    model_config = ConfigDict(frozen=True)


class NotificationManager:
    """Thread-safe Notification Hub handling system notification dispatch and bounded history retention."""

    def __init__(self, max_history: int = 500) -> None:
        self._lock = threading.RLock()
        self._history: collections.deque[Notification] = collections.deque(maxlen=max_history)
        self._category_counts: Dict[NotificationCategory, int] = {cat: 0 for cat in NotificationCategory}

    def notify(
        self,
        category: NotificationCategory,
        title: str,
        message: str,
        target_service: str = "system",
    ) -> Notification:
        """Dispatch and record an in-memory notification."""
        with self._lock:
            n = Notification(
                category=category,
                title=title,
                message=message,
                target_service=target_service,
                timestamp=datetime.now(timezone.utc),
            )
            self._history.append(n)
            self._category_counts[category] += 1
            logger.info("Notification [%s]: %s - %s", category.value, title, message)
            return n

    def notify_service_failure(self, service_name: str, reason: str) -> Notification:
        """Send service failure notification."""
        return self.notify(
            category=NotificationCategory.SERVICE_FAILURE,
            title=f"Service Failure: {service_name}",
            message=f"Service '{service_name}' has failed: {reason}",
            target_service=service_name,
        )

    def notify_service_recovery(self, service_name: str) -> Notification:
        """Send service recovery notification."""
        return self.notify(
            category=NotificationCategory.SERVICE_RECOVERY,
            title=f"Service Recovered: {service_name}",
            message=f"Service '{service_name}' has returned to HEALTHY status.",
            target_service=service_name,
        )

    def notify_critical_alert(self, title: str, details: str, service_name: str = "system") -> Notification:
        """Send critical alert notification."""
        return self.notify(
            category=NotificationCategory.CRITICAL_ALERT,
            title=f"CRITICAL: {title}",
            message=details,
            target_service=service_name,
        )

    def notify_heartbeat_failure(self, service_name: str, latency_ms: float) -> Notification:
        """Send heartbeat failure notification."""
        return self.notify(
            category=NotificationCategory.HEARTBEAT_FAILURE,
            title=f"Heartbeat Stale: {service_name}",
            message=f"Service '{service_name}' heartbeat timed out or latency excessive ({latency_ms:.1f} ms).",
            target_service=service_name,
        )

    def get_notification_history(self, limit: Optional[int] = None) -> List[Notification]:
        """Get notification history up to limit."""
        with self._lock:
            items = list(self._history)
            return items[-limit:] if limit else items

    def get_notifications_by_category(self, category: NotificationCategory) -> List[Notification]:
        """Get stored notifications for a specific category."""
        with self._lock:
            return [n for n in self._history if n.category == category]

    def get_counts(self) -> Dict[str, int]:
        """Get notification counts per category."""
        with self._lock:
            return {cat.value: count for cat, count in self._category_counts.items()}

    def clear(self) -> None:
        """Clear notification history and reset counters."""
        with self._lock:
            self._history.clear()
            for cat in NotificationCategory:
                self._category_counts[cat] = 0
