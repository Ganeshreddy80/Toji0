"""Immutable Pydantic models for the Institutional Memory Platform.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MemoryMetadata(BaseModel):
    """Common metadata tracking parameters for every institutional memory."""

    memory_id: str
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    originating_subsystem: str
    originating_event: str
    author: str  # human or AI
    confidence_score: float = 1.0
    lineage_parent_ids: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class TradeMemory(BaseModel):
    """Memory representation of a trade execution outcome."""

    metadata: MemoryMetadata
    trade_id: str
    symbol: str
    quantity: float
    entry_price: float
    exit_price: float
    slippage_ms: float
    execution_quality: str

    model_config = ConfigDict(frozen=True)


class PositionMemory(BaseModel):
    """Memory representing a position lifecycle."""

    metadata: MemoryMetadata
    position_id: str
    symbol: str
    average_cost: float
    realized_pnl: float
    holding_duration_seconds: float

    model_config = ConfigDict(frozen=True)


class StrategyMemory(BaseModel):
    """Memory representing strategy parameters state."""

    metadata: MemoryMetadata
    strategy_id: str
    version_tag: str
    sharpe: float
    sortino: float
    drawdown: float
    parameters: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ResearchMemory(BaseModel):
    """Memory of hypotheses and backtesting reports."""

    metadata: MemoryMetadata
    hypothesis_id: str
    experiment_name: str
    sharpe: float
    drawdown: float
    validated: bool

    model_config = ConfigDict(frozen=True)


class RiskMemory(BaseModel):
    """Memory representing VaR metrics and compliance breaches."""

    metadata: MemoryMetadata
    var_limit: float
    cvar_limit: float
    leverage_limit: float
    active_breaches_count: int
    kill_switch_active: bool

    model_config = ConfigDict(frozen=True)


class ObservabilityMemory(BaseModel):
    """Memory representing resource loads and latency percentiles."""

    metadata: MemoryMetadata
    mean_latency_ms: float
    p95_latency_ms: float
    cpu_usage_pct: float
    memory_used_mb: float

    model_config = ConfigDict(frozen=True)


class AIMemory(BaseModel):
    """Memory representing LLM advisory reports."""

    metadata: MemoryMetadata
    recommendation_id: str
    action: str
    reasoning: str
    confidence: float

    model_config = ConfigDict(frozen=True)


class HumanMemory(BaseModel):
    """Memory representing human governance reviews."""

    metadata: MemoryMetadata
    approval_id: str
    action_approved: str
    comments: str
    decision_timestamp: datetime

    model_config = ConfigDict(frozen=True)


class Relationship(BaseModel):
    """Linkage mapping parents to children nodes."""

    parent_id: str
    child_id: str
    link_type: str  # lineage, parameter, correction

    model_config = ConfigDict(frozen=True)


class LessonLearnedRecord(BaseModel):
    """Structured lesson extracted from trading sessions outcomes."""

    lesson_id: str
    trade_id: str
    observation: str
    hypothesis: str
    evidence: str
    confidence: float
    recommended_action: str
    validation_status: str  # PENDING_RESEARCH, VALIDATED, REJECTED
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class ReplaySnapshot(BaseModel):
    """Reconstructed context state at historical timestamp."""

    snapshot_timestamp: datetime
    trades: List[TradeMemory] = Field(default_factory=list)
    positions: List[PositionMemory] = Field(default_factory=list)
    strategies: List[StrategyMemory] = Field(default_factory=list)
    risks: List[RiskMemory] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)
