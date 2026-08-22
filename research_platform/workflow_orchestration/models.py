"""Immutable Pydantic models for the Workflow Orchestration Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


class WorkflowStepName(str, Enum):
    RESEARCH = "RESEARCH"
    BACKTEST = "BACKTEST"
    WALK_FORWARD = "WALK_FORWARD"
    PAPER_TRADING = "PAPER_TRADING"
    RISK_REVIEW = "RISK_REVIEW"
    AI_REVIEW = "AI_REVIEW"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    DEPLOYMENT = "DEPLOYMENT"
    MONITORING = "MONITORING"
    RETIREMENT = "RETIREMENT"


class WorkflowStep(BaseModel):
    """A single sequential step inside a strategy lifecycle workflow."""

    name: WorkflowStepName
    status: WorkflowStatus = WorkflowStatus.PENDING
    retries: int = 0
    max_retries: int = 3
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(frozen=True)


class WorkflowApproval(BaseModel):
    """An authorization token log produced by governance checkpoint entities."""

    step_name: WorkflowStepName
    approver: str  # e.g. RISK, AI, HUMAN, COMMITTEE
    signature: str
    approved: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class WorkflowInstance(BaseModel):
    """The state track record instance of an active sequential strategy workflow."""

    instance_id: str
    strategy_id: str
    current_step_index: int = 0
    status: WorkflowStatus = WorkflowStatus.PENDING
    steps: List[WorkflowStep] = Field(default_factory=list)
    approvals: List[WorkflowApproval] = Field(default_factory=list)
    transition_log: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
