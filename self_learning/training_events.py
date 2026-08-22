"""Immutable Training Pipeline Event Models (Sprint 11B)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class PipelineCreated(BaseModel):
    """Event published when a training pipeline is created."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="PipelineCreated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pipeline_id: str
    pipeline_name: str
    model_id: str
    dataset_id: str

    model_config = ConfigDict(frozen=True)


class PipelineQueued(BaseModel):
    """Event published when a training pipeline is placed in the scheduling queue."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="PipelineQueued")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pipeline_id: str
    priority: int

    model_config = ConfigDict(frozen=True)


class PipelineStarted(BaseModel):
    """Event published when training pipeline execution begins."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="PipelineStarted")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pipeline_id: str
    model_id: str

    model_config = ConfigDict(frozen=True)


class PipelineCompleted(BaseModel):
    """Event published when training pipeline execution completes successfully."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="PipelineCompleted")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pipeline_id: str
    metrics: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class PipelineFailed(BaseModel):
    """Event published when training pipeline execution fails."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="PipelineFailed")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pipeline_id: str
    error_message: str

    model_config = ConfigDict(frozen=True)


class PipelineCancelled(BaseModel):
    """Event published when a training pipeline is cancelled."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="PipelineCancelled")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pipeline_id: str
    reason: str = Field(default="User cancelled")

    model_config = ConfigDict(frozen=True)


class CheckpointSaved(BaseModel):
    """Event published when a training checkpoint is saved."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="CheckpointSaved")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    checkpoint_id: str
    pipeline_id: str
    epoch: int

    model_config = ConfigDict(frozen=True)


class ArtifactRegistered(BaseModel):
    """Event published when a training artifact is registered."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="ArtifactRegistered")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    artifact_id: str
    pipeline_id: str
    artifact_name: str
    version: str

    model_config = ConfigDict(frozen=True)
