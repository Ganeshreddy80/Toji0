"""Alert engine creating warning alert cards.
"""

from __future__ import annotations

from research_platform.monitoring.models import AlertCard


class AlertEngine:
    """Builds alert notifications based on severity levels."""

    def compile_alert(self, alert_id: str, level: str, source: str, message: str) -> AlertCard:
        return AlertCard(
            alert_id=alert_id,
            level=level,
            source=source,
            message=message
        )
