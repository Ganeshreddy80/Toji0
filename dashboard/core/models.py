"""Pydantic V2 models for the Dashboard Platform subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from dashboard.core.enums import HealthStatus


class SubsystemHealth(BaseModel):
    """Immutable model representing health details of a single subsystem."""

    status: HealthStatus = Field(..., description="Operational status.")
    last_update: datetime = Field(..., description="Timestamp of last message/event.")
    processing_latency_ms: float = Field(..., description="Event processing latency in milliseconds.")
    message_count: int = Field(..., description="Number of events received.")
    replay_status: str = Field(..., description="Replay status description (e.g. LIVE, REPLAYING).")

    model_config = ConfigDict(frozen=True)


class DashboardSnapshot(BaseModel):
    """Consolidated state snapshot representing the entire trading platform state."""

    snapshot_id: str = Field(..., description="Unique UUID for this snapshot.")
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    market_state: Optional[Dict[str, Any]] = Field(default=None, description="Market State payload.")
    pattern_state: Optional[Dict[str, Any]] = Field(default=None, description="Pattern State payload.")
    pattern_quality: Optional[Dict[str, Any]] = Field(default=None, description="Pattern Quality payload.")
    confluence: Optional[Dict[str, Any]] = Field(default=None, description="Confluence State payload.")
    strategy: Optional[Dict[str, Any]] = Field(default=None, description="Strategy State payload.")
    trading_context: Optional[Dict[str, Any]] = Field(default=None, description="Trading Context payload.")
    risk_assessment: Optional[Dict[str, Any]] = Field(default=None, description="Risk Assessment payload.")
    position_size: Optional[Dict[str, Any]] = Field(default=None, description="Position Size payload.")
    execution_state: Optional[Dict[str, Any]] = Field(default=None, description="Execution State payload.")
    portfolio_state: Optional[Dict[str, Any]] = Field(default=None, description="Portfolio State payload.")
    health_status: Dict[str, SubsystemHealth] = Field(default_factory=dict, description="Platform health status per subsystem.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Snapshot timestamp.",
    )
    version: str = Field(default="1.0.0", description="Dashboard Snapshot version.")

    model_config = ConfigDict(frozen=True)


class HistoricalEvent(BaseModel):
    """Immutable model representing an event captured in the event timeline."""

    event_id: str = Field(..., description="Unique UUID for the log event.")
    timestamp: datetime = Field(..., description="Timestamp when event was published.")
    subsystem: str = Field(..., description="Source subsystem (e.g., MIL, PAE, CE).")
    event_name: str = Field(..., description="Published event class name.")
    symbol: str = Field(..., description="Target symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    latency_ms: float = Field(..., description="Time taken to process event.")
    severity: str = Field(..., description="Severity classification.")
    payload: Dict[str, Any] = Field(..., description="Raw payload of the event.")

    model_config = ConfigDict(frozen=True)
