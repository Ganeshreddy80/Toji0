"""Pydantic schemas for quantitative research experiments tracking."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ExperimentStatus(enum.Enum):
    """Execution status state of an experiment run."""

    CREATED = "created"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ARCHIVED = "archived"


class ResearchExperiment(BaseModel):
    """Canonical model for defining a quantitative research experiment."""

    experiment_id: str = Field(..., description="Unique UUID of the experiment")
    name: str = Field(..., description="Short descriptive name of the research idea")
    version: str = Field(default="1.0.0", description="Semantic version of research definition")
    description: str = Field(..., description="Detailed description of hypothesis and expected edge")
    tags: list[str] = Field(default_factory=list, description="Categorization tags (e.g. momentum, futures)")
    dependencies: list[str] = Field(
        default_factory=list, description="IDs of other research experiments this depends on"
    )
    dataset_ref: str = Field(..., description="Reference to dataset identifier in platform storage")
    feature_refs: list[str] = Field(
        default_factory=list, description="List of feature store calculator names used"
    )
    asset_universe: list[str] = Field(..., description="List of tradeable asset symbols in scope")
    market_regime: str | None = Field(default=None, description="Market condition targeting (e.g. ranging)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class ExperimentRun(BaseModel):
    """Track record of a specific execution of a ResearchExperiment."""

    run_id: str = Field(...)
    experiment_id: str = Field(...)
    status: ExperimentStatus = Field(default=ExperimentStatus.CREATED)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = Field(default=None)
    metrics: dict[str, float] = Field(default_factory=dict, description="Calculated results metrics")
    logs: list[str] = Field(default_factory=list, description="Runtime execution logs trace")
    notes: str | None = Field(default=None, description="Qualitative notes by the researcher")

    model_config = {"frozen": True}


class ExperimentResult(BaseModel):
    """Result artifact of a successfully executed ExperimentRun."""

    result_id: str = Field(...)
    run_id: str = Field(...)
    metrics: dict[str, float] = Field(..., description="Core metrics (Sharpe, Drawdown, p-value)")
    plots: dict[str, str] = Field(default_factory=dict, description="Asset path links to generated plot images")
    conclusion: str = Field(..., description="Quant conclusions and validation check summaries")

    model_config = {"frozen": True}
