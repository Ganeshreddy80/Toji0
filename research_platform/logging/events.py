"""R52 Logging event models for EventBus publishing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid


class LogEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEventPublished(LogEvent):
    action: str
    actor: str
    success: bool


class TradeEventPublished(LogEvent):
    order_id: str
    symbol: str
    status: str


class ErrorEventPublished(LogEvent):
    component: str
    error_type: str
    message: str
