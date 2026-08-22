"""Alert System generating risk alert triggers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from research_platform.risk_management.models import RiskAlert


class RiskAlertSystem:
    """Publishes warnings of varying severity levels through the Event Bus."""

    @staticmethod
    def create_alert(severity: str, category: str, message: str) -> RiskAlert:
        """Construct standard RiskAlert."""
        return RiskAlert(
            alert_id=str(uuid.uuid4()),
            severity=severity,
            category=category,
            message=message
        )
