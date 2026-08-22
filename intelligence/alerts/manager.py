"""Alert Manager for triggering and managing prioritized alerts."""

from __future__ import annotations

import uuid
import threading
from datetime import datetime, timezone
from intelligence.models import Alert, AlertLevel


class AlertManager:
    """Manages thread-safe creation, storage, and filtering of prioritized system and market alerts."""

    def __init__(self) -> None:
        """Initialize the AlertManager."""
        self._alerts: list[Alert] = []
        self._lock = threading.Lock()

    def trigger_alert(
        self,
        symbol: str,
        level: AlertLevel,
        title: str,
        message: str,
    ) -> Alert:
        """Create and record an alert.

        Args:
            symbol: Target symbol.
            level: Severity level.
            title: Short description.
            message: Detailed explanation.

        Returns:
            The created Alert object.
        """
        alert = Alert(
            alert_id=f"alert-{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            level=level,
            title=title,
            message=message,
            timestamp=datetime.now(timezone.utc),
        )

        with self._lock:
            self._alerts.append(alert)

        return alert

    def get_alerts(
        self,
        min_level: AlertLevel | None = None,
        symbol: str | None = None,
    ) -> list[Alert]:
        """Retrieve recorded alerts, optionally filtered by level and/or symbol.

        Args:
            min_level: Optional minimum severity level.
            symbol: Optional symbol filter.

        Returns:
            Filtered list of Alert objects.
        """
        # Map levels to integer weights for threshold filtering
        level_weights = {
            AlertLevel.LOW: 1,
            AlertLevel.MEDIUM: 2,
            AlertLevel.HIGH: 3,
            AlertLevel.CRITICAL: 4,
        }

        min_weight = level_weights.get(min_level) if min_level else 0

        with self._lock:
            filtered = []
            for alert in self._alerts:
                if symbol and alert.symbol != symbol:
                    continue
                if min_level:
                    weight = level_weights.get(alert.level, 0)
                    if weight < min_weight:
                        continue
                filtered.append(alert)
            return filtered

    def clear_alerts(self) -> None:
        """Clear all recorded alerts."""
        with self._lock:
            self._alerts.clear()
