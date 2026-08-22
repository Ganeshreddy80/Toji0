"""Immutable Pydantic models for the Monitoring Center.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field


class ServiceStatus(BaseModel):
    """Heartbeat record for an active platform component."""

    service_name: str
    is_alive: bool
    response_time_ms: float
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class AlertCard(BaseModel):
    """System error warning alert card."""

    alert_id: str
    level: str  # INFO, WARNING, CRITICAL
    source: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class MetricCounter(BaseModel):
    """Observed aggregated metric counter value."""

    metric_name: str
    value: int

    model_config = ConfigDict(frozen=True)
