"""State Recovery event models published to the EventBus.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class RecoveryEvent(BaseModel):
    """Base event representation for recovery operations."""
    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CheckpointSaved(RecoveryEvent):
    """Emitted when a checkpoint completes saving successfully."""
    checkpoint_id: str


class CheckpointLoaded(RecoveryEvent):
    """Emitted when a checkpoint is restored successfully."""
    checkpoint_id: str


class RecoveryStarted(RecoveryEvent):
    """Emitted when the startup recovery engine begins execution."""
    session_id: str


class RecoveryCompleted(RecoveryEvent):
    """Emitted when startup recovery finishes successfully."""
    session_id: str
    duration_ms: float


class RecoveryFailed(RecoveryEvent):
    """Emitted when startup recovery fails to restore state."""
    session_id: str
    error_message: str


class IntegrityCheckFailed(RecoveryEvent):
    """Emitted when a checkpoint fails hash integrity audits."""
    checkpoint_id: str
    reason: str


class SystemCrashed(RecoveryEvent):
    """Emitted when crash detection detects an unclean platform termination."""
    detected_at: datetime
    previous_heartbeat_timestamp: datetime
    reason: str
