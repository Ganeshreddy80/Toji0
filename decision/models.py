"""Canonical Pydantic models and Enums for the Toji Decision Engine."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class DecisionState(enum.Enum):
    """Priority recommendation state for a market asset."""

    IGNORE = "IGNORE"
    WATCH = "WATCH"
    PREPARE = "PREPARE"
    READY = "READY"
    ENTER = "ENTER"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    EXIT = "EXIT"
    EMERGENCY_EXIT = "EMERGENCY_EXIT"


class TimelineState(enum.Enum):
    """Lifecycle track states for a logged investment decision."""

    CREATED = "Created"
    UPDATED = "Updated"
    CONFIRMED = "Confirmed"
    EXPIRED = "Expired"
    CANCELLED = "Cancelled"
    EXECUTED = "Executed"
    CLOSED = "Closed"


class CommitteeVote(BaseModel):
    """Individual vote and rationale submitted by a specialized committee."""

    committee_name: str = Field(..., description="Name of the evaluating committee")
    vote_state: DecisionState = Field(..., description="Voted decision state outcome")
    score: float = Field(..., ge=-1.0, le=1.0, description="Normalized score (typically 0.0 to 1.0, -1.0 for exit)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Assessed confidence level")
    metrics: dict[str, Any] = Field(default_factory=dict, description="Supporting quantitative metrics evaluated")
    reason: str = Field(..., description="Detailed textual rationale")

    model_config = {"frozen": True}


class InvestmentDecision(BaseModel):
    """Final compiled recommendation and explainable audit trail from the Investment Committee."""

    decision_id: str = Field(..., description="Unique decision ID")
    symbol: str = Field(..., description="Asset symbol evaluated")
    overall_score: float = Field(..., ge=-1.0, le=1.0, description="Consensus scoring index")
    final_recommendation: DecisionState = Field(..., description="Voted final decision state instruction")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall average confidence weight")
    votes: list[CommitteeVote] = Field(..., description="Individually submitted committee votes")
    supporting_evidence: list[str] = Field(default_factory=list, description="Keys/descriptions of supporting evidence")
    contradicting_evidence: list[str] = Field(default_factory=list, description="Keys/descriptions of conflicting data")
    rule_references: list[str] = Field(default_factory=list, description="IDs of active knowledge rules applied")
    research_references: list[str] = Field(default_factory=list, description="IDs of source backtests/experiments referenced")
    risk_summary: str = Field(..., description="Consolidated risk overview")
    timing_summary: str = Field(..., description="Consolidated timing overview")
    expiry_time: datetime = Field(..., description="When this decision recommendation expires")
    review_time: datetime = Field(..., description="Next scheduled re-evaluation checkpoint")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class TimelineEvent(BaseModel):
    """Historical timeline state transition audit event."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    state: TimelineState = Field(..., description="Target timeline state transitioned into")
    details: str = Field(..., description="Context explanation of the state change")

    model_config = {"frozen": True}


class JournalEntry(BaseModel):
    """Stored record tracing a decision lifecycle, actual market outcome, and retrospect lessons."""

    decision_id: str = Field(..., description="Unique decision ID")
    decision: InvestmentDecision = Field(..., description="The original compiled decision parameters")
    timeline_history: list[TimelineEvent] = Field(default_factory=list, description="Sequential audit timeline events")
    outcome: str | None = Field(default=None, description="Actual market performance outcome details")
    is_correct: bool | None = Field(default=None, description="Correctness evaluation relative to direction")
    lessons: list[str] = Field(default_factory=list, description="Lessons logged for subsequent optimizer passes")
    closed_at: datetime | None = Field(default=None, description="Timestamp when decision was marked Closed")

    model_config = {
        "arbitrary_types_allowed": True,
    }
