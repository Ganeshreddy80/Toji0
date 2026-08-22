"""Thread-safe memory repository caching dashboard snapshots and alerts.
"""

from __future__ import annotations

import collections
import threading
from typing import List, Optional
from research_platform.operations_center.interfaces import IOperationsRepository
from research_platform.operations_center.dashboard_models import (
    AlertCard,
    DashboardSnapshot,
)


class OperationsRepository(IOperationsRepository):
    """Memory-backed store caching active dashboard snapshots with rolling playback histories."""

    def __init__(self, max_history_len: int = 100) -> None:
        self._lock = threading.Lock()
        self._snapshots = collections.deque(maxlen=max_history_len)
        self._alerts: List[AlertCard] = []

    def save_snapshot(self, snapshot: DashboardSnapshot) -> None:
        with self._lock:
            self._snapshots.append(snapshot)

    def get_latest_snapshot(self) -> Optional[DashboardSnapshot]:
        with self._lock:
            if self._snapshots:
                return self._snapshots[-1]
            return None

    def list_historical_snapshots(self) -> List[DashboardSnapshot]:
        with self._lock:
            return list(self._snapshots)

    def save_alert(self, alert: AlertCard) -> None:
        with self._lock:
            self._alerts.append(alert)

    def list_active_alerts(self) -> List[AlertCard]:
        with self._lock:
            return list(self._alerts)

    def clear_all(self) -> None:
        with self._lock:
            self._snapshots.clear()
            self._alerts.clear()
