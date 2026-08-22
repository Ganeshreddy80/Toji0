"""Pipeline state models for the Self Learning Engine (Sprint 11B).

All models are Pydantic V2 with frozen=True to guarantee immutability.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class PipelineStatus(str, Enum):
    """Lifecycle state of a training pipeline."""

    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RETRYING = "RETRYING"


class PipelineConfig(BaseModel):
    """Immutable configuration for a training pipeline."""

    pipeline_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Pipeline name.")
    model_id: str = Field(..., description="Target model identifier.")
    dataset_id: str = Field(..., description="Training dataset identifier.")
    priority: int = Field(default=0, description="Priority level (higher number = higher priority).")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts.")
    timeout_seconds: float = Field(default=60.0, gt=0.0, description="Execution timeout in seconds.")
    cpu_cores: float = Field(default=2.0, gt=0.0, description="CPU cores requirement.")
    memory_mb: float = Field(default=4096.0, gt=0.0, description="Memory requirement in MB.")
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_advisory_only: bool = Field(default=True, description="Advisory flag.")

    model_config = ConfigDict(frozen=True)


class PipelineRecord(BaseModel):
    """Immutable state snapshot of a training pipeline execution."""

    pipeline_id: str = Field(..., description="Associated pipeline identifier.")
    config: PipelineConfig = Field(..., description="Pipeline configuration.")
    status: PipelineStatus = Field(default=PipelineStatus.CREATED)
    current_retry: int = Field(default=0, ge=0)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)
