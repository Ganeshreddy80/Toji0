"""Immutable Pydantic models for the Experiment Manager.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ReproducibilitySnapshot(BaseModel):
    """Snapshot guaranteeing exact quant experiment reproducibility."""

    random_seed: int
    dataset_hash: str
    git_hash: str
    config_id: str
    result_hash: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class Experiment(BaseModel):
    """A quant research experiment entry."""

    experiment_id: str
    name: str
    description: str
    tags: List[str] = Field(default_factory=list)
    group_id: str = "DEFAULT"
    status: str = "DRAFT"  # DRAFT, RUNNING, PAUSED, COMPLETED, ARCHIVED
    reproducibility: ReproducibilitySnapshot
    results: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class ExperimentComparison(BaseModel):
    """Comparison results across parameter sets, datasets, and exchanges."""

    experiment_ids: List[str]
    metric_differences: Dict[str, List[float]] = Field(default_factory=dict)
    differing_keys: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class LeaderboardEntry(BaseModel):
    """Leaderboard entry for score rankings."""

    strategy_id: str
    score: float
    rank: int

    model_config = ConfigDict(frozen=True)


class Leaderboard(BaseModel):
    """Leaderboard ranking experiment strategy outputs."""

    name: str
    entries: List[LeaderboardEntry] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
