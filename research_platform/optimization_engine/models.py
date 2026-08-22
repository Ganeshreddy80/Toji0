"""Immutable Pydantic models for the Optimization Engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ParameterDefinition(BaseModel):
    """Configuration constraints for a single strategy parameter."""

    name: str
    type: str  # int, float, categorical
    bounds: Optional[List[float]] = None  # [min, max]
    categorical_values: Optional[List[Any]] = None

    model_config = ConfigDict(frozen=True)


class ParameterSpace(BaseModel):
    """Grid or randomized parameter search spaces."""

    parameters: List[ParameterDefinition] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class ParameterCombination(BaseModel):
    """A specific parameter assignment instance."""

    values: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ObjectiveScore(BaseModel):
    """Computed outcomes over objectives."""

    metrics: Dict[str, float] = Field(default_factory=dict)
    composite_score: float

    model_config = ConfigDict(frozen=True)


class ConstraintResult(BaseModel):
    """Feasibility check outcomes."""

    is_violated: bool
    details: str

    model_config = ConfigDict(frozen=True)


class OptimizationTrial(BaseModel):
    """A single strategy evaluation run inside parameter sweeps."""

    trial_id: str
    parameters: ParameterCombination
    score: ObjectiveScore
    is_valid: bool
    constraint_result: ConstraintResult

    model_config = ConfigDict(frozen=True)


class ParetoFront(BaseModel):
    """Non-dominated trials boundary list."""

    non_dominated_trials: List[OptimizationTrial] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class WalkForwardWindow(BaseModel):
    """A single in-sample training and out-of-sample forward test window."""

    window_id: str
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    best_parameters: ParameterCombination
    in_sample_score: float
    out_of_sample_score: float

    model_config = ConfigDict(frozen=True)


class RobustnessMetrics(BaseModel):
    """Sensitivity analysis statistics."""

    sensitivity_gradient: float
    parameter_stability_score: float
    neighborhood_standard_deviation: float

    model_config = ConfigDict(frozen=True)


class SensitivityReport(BaseModel):
    """Parametric sensitivity maps."""

    parameter_name: str
    gradient_values: Dict[str, float] = Field(default_factory=dict)
    stability_rank: int

    model_config = ConfigDict(frozen=True)


class OptimizationConfiguration(BaseModel):
    """Sweeper algorithms configurations."""

    space: ParameterSpace
    objective_weights: Dict[str, float] = Field(default_factory=dict)
    constraint_limits: Dict[str, float] = Field(default_factory=dict)
    algorithm: str = "GRID"  # GRID, RANDOM, GENETIC, BAYESIAN
    num_trials: int = 100
    parallel_workers: int = 4

    model_config = ConfigDict(frozen=True)


class OptimizationResult(BaseModel):
    """Final optimization output reports."""

    best_trial: OptimizationTrial
    pareto_front: ParetoFront
    walk_forward_windows: List[WalkForwardWindow] = Field(default_factory=list)
    robustness_report: Dict[str, RobustnessMetrics] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class OptimizationRun(BaseModel):
    """Progress wrappers tracking execution."""

    run_id: str
    configuration: OptimizationConfiguration
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    result: Optional[OptimizationResult] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)
