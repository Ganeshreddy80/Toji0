"""State Recovery configuration models.
"""

from __future__ import annotations

from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class SnapshotType(str, Enum):
    """Trigger reasons for saving system snapshots."""
    MANUAL = "MANUAL"
    AUTOMATIC = "AUTOMATIC"
    TIMED = "TIMED"
    PRE_SHUTDOWN = "PRE_SHUTDOWN"
    PRE_UPGRADE = "PRE_UPGRADE"
    CRASH = "CRASH"


class Checkpoint(BaseModel):
    """Complete snapshot of the trading platform state at a point in time."""
    checkpoint_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    runtime_state: Dict[str, Any] = Field(default_factory=dict)
    portfolio_state: Dict[str, Any] = Field(default_factory=dict)
    positions_state: List[Dict[str, Any]] = Field(default_factory=list)
    orders_state: List[Dict[str, Any]] = Field(default_factory=list)
    trades_state: List[Dict[str, Any]] = Field(default_factory=list)
    scheduler_state: Dict[str, Any] = Field(default_factory=dict)
    strategies_state: List[Dict[str, Any]] = Field(default_factory=list)
    monitoring_state: Dict[str, Any] = Field(default_factory=dict)
    metrics_state: Dict[str, Any] = Field(default_factory=dict)
    integrity_hash: str = ""


class Snapshot(BaseModel):
    """Database-stored snapshot record."""
    snapshot_id: str
    checkpoint_id: str
    snapshot_type: SnapshotType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    description: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class RecoverySession(BaseModel):
    """Operational log session detailing a single startup recovery run."""
    session_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str  # STARTED, SUCCESS, FAILED
    stages_executed: List[str] = Field(default_factory=list)
    retry_count: int = 0
    duration_ms: float = 0.0
    error_message: Optional[str] = None


class RecoveryHistory(BaseModel):
    """Cumulative database log tracking historical recovery operations."""
    sessions: List[RecoverySession] = Field(default_factory=list)
