"""Pydantic event models emitted by the Continuous Runtime Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class RuntimeEvent(BaseModel):
    """Base event structure for all runtime changes."""
    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RuntimeStarted(RuntimeEvent):
    """Emitted when the continuous runtime loop starts."""
    status: str = "RUNNING"


class RuntimePaused(RuntimeEvent):
    """Emitted when the execution engine is paused."""
    status: str = "PAUSED"


class RuntimeResumed(RuntimeEvent):
    """Emitted when execution resumes."""
    status: str = "RUNNING"


class RuntimeStopped(RuntimeEvent):
    """Emitted when runtime is stopped."""
    status: str = "STOPPED"


class HeartbeatLogged(RuntimeEvent):
    """Periodic telemetry report emitted by the engine."""
    loop_latency_ms: float
    cpu_time_ms: float
    memory_mb: float
    event_count: int
    recovery_count: int
    loop_states: Dict[str, str] = Field(default_factory=dict)


class SubsystemFailed(RuntimeEvent):
    """Emitted when a subsystem loop execution raises an exception."""
    subsystem_name: str
    error_message: str


class SubsystemRecovered(RuntimeEvent):
    """Emitted when a previously degraded subsystem loop returns to normal execution."""
    subsystem_name: str
    retry_count: int
