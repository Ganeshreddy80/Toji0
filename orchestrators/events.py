"""Custom integration events for the system orchestrators."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from toji_platform.core.event_bus.events import BaseEvent
from toji_platform.core.types import EventId


@dataclass(frozen=True)
class SchedulerTick(BaseEvent):
    """Fired by the scheduler at specific times/intervals."""

    tick_type: str = "hourly"  # "market_open", "hourly", "funding", "economic_event", "eod", "manual"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class WorkflowStepExecuted(BaseEvent):
    """Fired by the workflow engine when a step finishes executing."""

    workflow_name: str = ""
    step_name: str = ""
    status: str = "success"  # "success", "failed"
    result: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AlertTriggered(BaseEvent):
    """Fired when risk boundaries are approached or active warnings are generated."""

    severity: str = "info"  # "info", "warning", "critical"
    alert_type: str = "general"
    message: str = ""
    symbol: str | None = None


@dataclass(frozen=True)
class OpportunityRanked(BaseEvent):
    """Fired when the scanner completes a universe run with ranked lists."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
