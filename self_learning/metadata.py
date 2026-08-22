"""Immutable Metadata Models for Self Learning Engine (Sprint 11A)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from self_learning.models.learning_models import SemanticVersion


class ModelMetadata(BaseModel):
    """Immutable metadata record attached to a registered ML model."""

    metadata_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = Field(..., description="Associated model identifier.")
    model_name: str = Field(..., description="Human-readable model name.")
    version: SemanticVersion = Field(default_factory=SemanticVersion)
    author: str = Field(default="SYSTEM")
    framework: str = Field(default="", description="ML framework (e.g. sklearn, pytorch).")
    input_features: List[str] = Field(default_factory=list)
    output_targets: List[str] = Field(default_factory=list)
    performance_notes: str = Field(default="")
    advisory_only: bool = Field(default=True, description="Advisory flag.")
    extra: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class DatasetMetadata(BaseModel):
    """Immutable metadata record for a registered dataset."""

    metadata_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dataset_id: str = Field(..., description="Associated dataset identifier.")
    dataset_name: str = Field(..., description="Human-readable dataset name.")
    version: SemanticVersion = Field(default_factory=SemanticVersion)
    data_source: str = Field(default="in-memory")
    schema: Dict[str, str] = Field(default_factory=dict, description="Column name → dtype.")
    row_count: int = Field(default=0, ge=0)
    description: str = Field(default="")
    extra: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class TrainingMetadata(BaseModel):
    """Immutable metadata record for a training run."""

    metadata_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="Associated training job identifier.")
    model_id: str = Field(..., description="Target model identifier.")
    dataset_id: str = Field(..., description="Training dataset identifier.")
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    result_metrics: Dict[str, float] = Field(default_factory=dict)
    duration_seconds: Optional[float] = Field(default=None, ge=0.0)
    notes: str = Field(default="")
    advisory_only: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
