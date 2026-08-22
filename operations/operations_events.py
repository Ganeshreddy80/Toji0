"""Immutable Operations & Monitoring Event Models for TOJI Platform (Sprint 12C)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class MetricsCollected(BaseModel):
    """Event published when a batch of metrics is collected."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="MetricsCollected")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metric_count: int
    collector_id: str = Field(default="default_collector")

    model_config = ConfigDict(frozen=True)


class AlertTriggered(BaseModel):
    """Event published when an operational alert condition is triggered."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="AlertTriggered")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    alert_id: str
    rule_name: str
    metric_name: str
    severity: str
    current_value: float
    threshold_value: float

    model_config = ConfigDict(frozen=True)


class AlertAcknowledged(BaseModel):
    """Event published when an active alert is acknowledged."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="AlertAcknowledged")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    alert_id: str
    acknowledged_by: str

    model_config = ConfigDict(frozen=True)


class AlertResolved(BaseModel):
    """Event published when an alert is resolved."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="AlertResolved")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    alert_id: str
    resolution_note: str

    model_config = ConfigDict(frozen=True)


class AuditEntryCreated(BaseModel):
    """Event published when an immutable audit entry is recorded."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="AuditEntryCreated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entry_id: str
    action: str
    actor: str
    resource_type: str
    resource_id: str

    model_config = ConfigDict(frozen=True)


class DashboardGenerated(BaseModel):
    """Event published when an operational dashboard view is generated."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="DashboardGenerated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    view_id: str
    overall_status: str

    model_config = ConfigDict(frozen=True)


class ReportGenerated(BaseModel):
    """Event published when an operational report is generated."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="ReportGenerated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    report_id: str
    report_type: str

    model_config = ConfigDict(frozen=True)


class OperationsCycleCompleted(BaseModel):
    """Event published when a full operational monitoring cycle completes."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="OperationsCycleCompleted")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cycle_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metrics_count: int
    active_alerts_count: int
    overall_health: str

    model_config = ConfigDict(frozen=True)
