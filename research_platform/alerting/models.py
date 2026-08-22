"""R54 Alerting & Notification Framework — models."""

from __future__ import annotations

import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class AlertChannel(str, Enum):
    LOG = "LOG"
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"
    CONSOLE = "CONSOLE"
    DATABASE = "DATABASE"
    TELEGRAM = "TELEGRAM"


class AlertStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    SUPPRESSED = "SUPPRESSED"
    FAILED = "FAILED"


class Alert(BaseModel):
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    message: str
    severity: AlertSeverity
    source: str = "TOJI"
    category: str = "GENERAL"
    status: AlertStatus = AlertStatus.PENDING
    channels: List[AlertChannel] = Field(default_factory=lambda: [AlertChannel.LOG])
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None


class AlertRule(BaseModel):
    rule_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    condition_fn: str = ""          # textual descriptor — execution is in code
    severity: AlertSeverity = AlertSeverity.MEDIUM
    channels: List[AlertChannel] = Field(default_factory=lambda: [AlertChannel.LOG])
    cooldown_sec: float = 300.0     # minimum interval between repeated firings
    enabled: bool = True
    fire_count: int = 0
    last_fired_at: Optional[datetime] = None


class NotificationResult(BaseModel):
    alert_id: str
    channel: AlertChannel
    success: bool
    error: Optional[str] = None
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
