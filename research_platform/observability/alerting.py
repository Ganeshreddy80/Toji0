"""Alert Engine generating and routing notifications.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from research_platform.observability.models import Alert


class AlertEngine:
    """Dispatches alerts with varying severity levels."""

    @staticmethod
    def create_alert(severity: str, message: str) -> Alert:
        return Alert(
            alert_id=str(uuid.uuid4()),
            severity=severity,
            message=message
        )
