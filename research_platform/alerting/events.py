"""R54 Alerting events for EventBus publishing."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class AlertEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AlertFired(AlertEvent):
    alert_id: str
    title: str
    severity: str
    source: str


class AlertAcknowledged(AlertEvent):
    alert_id: str
    acknowledged_by: str = "SYSTEM"


class AlertSuppressed(AlertEvent):
    alert_id: str
    reason: str = ""
