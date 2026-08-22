"""Immutable Pydantic models for the Paper Control Console.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConsoleCommand(BaseModel):
    """An executed CLI control command record."""

    command_id: str
    command_name: str  # START_SESSION, STOP_SESSION, SET_ROUTING_MODE, SHOW_METRICS
    parameters: Dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "SUCCESS"  # SUCCESS, FAILED
    error_message: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class ConsoleSessionSummary(BaseModel):
    """Real-time dashboard session metrics card summary."""

    account_id: str
    equity: float
    cash: float
    realized_pnl: float
    unrealized_pnl: float
    drawdown: float
    routing_mode: str  # SIMULATION, PAPER, LIVE
    is_session_active: bool
    last_refresh_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class ConsoleState(BaseModel):
    """Current state parameters of the dashboard console."""

    active_command_count: int = 0
    alerts_triggered_count: int = 0
    system_status: str = "ONLINE"  # ONLINE, DEGRADED, OFFLINE

    model_config = ConfigDict(frozen=True)
