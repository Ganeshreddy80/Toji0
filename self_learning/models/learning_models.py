"""Immutable domain models for the Self Learning Engine (Sprint 11A).

All models are Pydantic V2 with frozen=True to guarantee immutability
throughout the advisory-only ML lifecycle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ModelStatus(str, Enum):
    """Lifecycle state of a registered ML model."""

    REGISTERED = "REGISTERED"
    LOADING = "LOADING"
    LOADED = "LOADED"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DEPRECATED = "DEPRECATED"
    ERROR = "ERROR"


class DatasetStatus(str, Enum):
    """Lifecycle state of a registered dataset."""

    REGISTERED = "REGISTERED"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    INVALID = "INVALID"
    DEPRECATED = "DEPRECATED"


class TrainingJobStatus(str, Enum):
    """Execution state of a training job."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class FeatureType(str, Enum):
    """Data type classification for stored features."""

    NUMERIC = "NUMERIC"
    CATEGORICAL = "CATEGORICAL"
    BOOLEAN = "BOOLEAN"
    TIMESTAMP = "TIMESTAMP"
    EMBEDDING = "EMBEDDING"


# ---------------------------------------------------------------------------
# Immutable Domain Models
# ---------------------------------------------------------------------------

class SemanticVersion(BaseModel):
    """Immutable semantic version (MAJOR.MINOR.PATCH)."""

    major: int = Field(default=0, ge=0)
    minor: int = Field(default=1, ge=0)
    patch: int = Field(default=0, ge=0)

    model_config = ConfigDict(frozen=True)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump_patch(self) -> "SemanticVersion":
        return SemanticVersion(major=self.major, minor=self.minor, patch=self.patch + 1)

    def bump_minor(self) -> "SemanticVersion":
        return SemanticVersion(major=self.major, minor=self.minor + 1, patch=0)

    def bump_major(self) -> "SemanticVersion":
        return SemanticVersion(major=self.major + 1, minor=0, patch=0)

    def as_tuple(self) -> tuple:
        return (self.major, self.minor, self.patch)


class ModelRecord(BaseModel):
    """Immutable record of a registered ML model."""

    model_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Human-readable model name.")
    version: SemanticVersion = Field(default_factory=SemanticVersion)
    status: ModelStatus = Field(default=ModelStatus.REGISTERED)
    model_type: str = Field(default="generic", description="Model algorithm family.")
    description: str = Field(default="")
    tags: List[str] = Field(default_factory=list)
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True, description="Advisory flag — never permits autonomous execution.")

    model_config = ConfigDict(frozen=True)


class DatasetRecord(BaseModel):
    """Immutable record of a registered dataset."""

    dataset_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Dataset identifier name.")
    version: SemanticVersion = Field(default_factory=SemanticVersion)
    status: DatasetStatus = Field(default=DatasetStatus.REGISTERED)
    description: str = Field(default="")
    feature_columns: List[str] = Field(default_factory=list)
    target_column: Optional[str] = Field(default=None)
    row_count: int = Field(default=0, ge=0)
    column_count: int = Field(default=0, ge=0)
    tags: List[str] = Field(default_factory=list)
    schema_metadata: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = Field(default="in-memory")

    model_config = ConfigDict(frozen=True)


class FeatureRecord(BaseModel):
    """Immutable record of a single feature in the feature store."""

    feature_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Feature name.")
    feature_type: FeatureType = Field(default=FeatureType.NUMERIC)
    value: Any = Field(default=None, description="Current feature value.")
    description: str = Field(default="")
    tags: List[str] = Field(default_factory=list)
    source_dataset_id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class TrainingJobRecord(BaseModel):
    """Immutable snapshot of a training job lifecycle state."""

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = Field(..., description="Target model identifier.")
    dataset_id: str = Field(..., description="Training dataset identifier.")
    status: TrainingJobStatus = Field(default=TrainingJobStatus.PENDING)
    description: str = Field(default="")
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    result_metrics: Dict[str, float] = Field(default_factory=dict)
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class FeaturePipelineOutput(BaseModel):
    """Immutable output produced by a feature pipeline execution."""

    pipeline_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str = Field(..., description="Pipeline identifier name.")
    features: Dict[str, Any] = Field(default_factory=dict)
    validation_passed: bool = Field(default=True)
    validation_errors: List[str] = Field(default_factory=list)
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    input_feature_count: int = Field(default=0, ge=0)
    output_feature_count: int = Field(default=0, ge=0)

    model_config = ConfigDict(frozen=True)
