"""Immutable Model Evaluation Event Models for the Self Learning Engine (Sprint 11C)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class EvaluationCreated(BaseModel):
    """Event published when an evaluation task is created."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="EvaluationCreated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluation_id: str
    model_id: str
    dataset_id: str

    model_config = ConfigDict(frozen=True)


class EvaluationStarted(BaseModel):
    """Event published when evaluation execution begins."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="EvaluationStarted")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluation_id: str
    model_id: str

    model_config = ConfigDict(frozen=True)


class EvaluationCompleted(BaseModel):
    """Event published when evaluation completes successfully."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="EvaluationCompleted")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluation_id: str
    model_id: str
    accuracy: float
    f1_score: float

    model_config = ConfigDict(frozen=True)


class EvaluationFailed(BaseModel):
    """Event published when evaluation fails."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="EvaluationFailed")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluation_id: str
    model_id: str
    error_message: str

    model_config = ConfigDict(frozen=True)


class EvaluationCancelled(BaseModel):
    """Event published when evaluation is cancelled."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="EvaluationCancelled")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluation_id: str
    reason: str = Field(default="User cancelled")

    model_config = ConfigDict(frozen=True)


class BenchmarkCompleted(BaseModel):
    """Event published when a multi-model benchmark is completed."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="BenchmarkCompleted")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    benchmark_id: str
    top_model_id: str
    model_count: int

    model_config = ConfigDict(frozen=True)


class PromotionEvaluated(BaseModel):
    """Event published when a promotion rule evaluation completes."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="PromotionEvaluated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_id: str
    is_eligible: bool
    reasons: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class LeaderboardUpdated(BaseModel):
    """Event published when a leaderboard ranking is updated."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="LeaderboardUpdated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    leaderboard_name: str
    top_model_id: str
    ranked_count: int

    model_config = ConfigDict(frozen=True)
