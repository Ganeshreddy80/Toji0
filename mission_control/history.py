"""Thread-safe Bounded History Storage for Mission Control Monitoring (Sprint 10B)."""

from __future__ import annotations

import collections
from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class HealthTransitionRecord(BaseModel):
    """Immutable record of a service health status transition."""

    service_name: str = Field(..., description="Target service identifier.")
    previous_status: str = Field(..., description="Previous health status.")
    new_status: str = Field(..., description="New health status.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Transition timestamp.",
    )
    details: Optional[str] = Field(default=None, description="Optional transition details.")

    model_config = ConfigDict(frozen=True)


class BoundedHistory:
    """Thread-safe bounded history manager preventing unbounded memory growth."""

    def __init__(
        self,
        max_alerts: int = 1000,
        max_health_changes: int = 1000,
        max_notifications: int = 1000,
        max_metrics: int = 1000,
    ) -> None:
        self._lock = threading.RLock()
        self._alerts: collections.deque = collections.deque(maxlen=max_alerts)
        self._health_changes: collections.deque[HealthTransitionRecord] = collections.deque(maxlen=max_health_changes)
        self._notifications: collections.deque = collections.deque(maxlen=max_notifications)
        self._metrics: collections.deque[Dict[str, Any]] = collections.deque(maxlen=max_metrics)

    def add_alert(self, alert: Any) -> None:
        """Add alert record to bounded alert history."""
        with self._lock:
            self._alerts.append(alert)

    def add_health_change(self, record: HealthTransitionRecord) -> None:
        """Add health transition record to bounded history."""
        with self._lock:
            self._health_changes.append(record)

    def add_notification(self, notification: Any) -> None:
        """Add notification record to bounded notification history."""
        with self._lock:
            self._notifications.append(notification)

    def add_metric_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Add metric snapshot record to bounded metrics history."""
        with self._lock:
            self._metrics.append(snapshot)

    def get_alerts(self, limit: Optional[int] = None) -> List[Any]:
        """Get recent alerts up to limit."""
        with self._lock:
            items = list(self._alerts)
            return items[-limit:] if limit else items

    def get_health_changes(self, limit: Optional[int] = None) -> List[HealthTransitionRecord]:
        """Get recent health changes up to limit."""
        with self._lock:
            items = list(self._health_changes)
            return items[-limit:] if limit else items

    def get_notifications(self, limit: Optional[int] = None) -> List[Any]:
        """Get recent notifications up to limit."""
        with self._lock:
            items = list(self._notifications)
            return items[-limit:] if limit else items

    def get_metrics_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent metric snapshots up to limit."""
        with self._lock:
            items = list(self._metrics)
            return items[-limit:] if limit else items

    def clear(self) -> None:
        """Clear all stored history collections."""
        with self._lock:
            self._alerts.clear()
            self._health_changes.clear()
            self._notifications.clear()
            self._metrics.clear()
