"""R54 Alert repository — in-memory deque with optional DB persistence."""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Deque, List, Optional

from research_platform.alerting.models import Alert, AlertStatus

logger = logging.getLogger(__name__)
MAX_ALERTS = 1000


class AlertRepository:
    """Thread-safe in-memory store for recent alerts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._alerts: Deque[Alert] = deque(maxlen=MAX_ALERTS)

    def save(self, alert: Alert) -> None:
        with self._lock:
            self._alerts.append(alert)

    def get_recent(self, limit: int = 100) -> List[Alert]:
        with self._lock:
            alerts = list(self._alerts)
        return alerts[-limit:]

    def get_by_severity(self, severity: str) -> List[Alert]:
        with self._lock:
            return [a for a in self._alerts if a.severity.value == severity]

    def get_unacknowledged(self) -> List[Alert]:
        with self._lock:
            return [a for a in self._alerts
                    if a.status not in (AlertStatus.ACKNOWLEDGED, AlertStatus.SUPPRESSED)]

    def acknowledge(self, alert_id: str) -> bool:
        from datetime import datetime, timezone
        with self._lock:
            for a in self._alerts:
                if a.alert_id == alert_id:
                    a.status = AlertStatus.ACKNOWLEDGED
                    a.acknowledged_at = datetime.now(timezone.utc)
                    return True
        return False

    def count(self) -> int:
        with self._lock:
            return len(self._alerts)
