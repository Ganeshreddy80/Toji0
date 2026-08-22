"""Immutable Pydantic models for the Experiment Management Platform.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExperimentRecord(BaseModel):
    """The complete captured registry record for a single strategy/alpha experiment."""

    experiment_id: str
    description: str
    dataset_hash: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    feature_versions: Dict[str, str] = Field(default_factory=dict)
    metrics: Dict[str, float] = Field(default_factory=dict)
    artifacts: List[str] = Field(default_factory=list)
    code_hash: str
    status: str = "PENDING"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class ReproducibilityCheck(BaseModel):
    """Replay validations check verifying parameters, dataset hashes, and metric diffs."""

    check_id: str
    experiment_id: str
    original_metrics: Dict[str, float]
    replayed_metrics: Dict[str, float]
    original_hash: str
    replayed_hash: str
    matched: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class ExperimentComparison(BaseModel):
    """Side-by-side comparative diff of multiple registered experiments."""

    comparison_id: str
    compared_ids: List[str]
    parameter_diffs: Dict[str, Any] = Field(default_factory=dict)
    metrics_comparison: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
