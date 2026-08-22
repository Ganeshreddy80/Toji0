"""Immutable Pydantic models for the Strategy Lab.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class StrategyParameters(BaseModel):
    """Container for strategy parameters."""

    params: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class EntryRule(BaseModel):
    """Entry trigger logic schema."""

    name: str
    condition_type: str  # SignalThreshold, Crossover, Breakout, Momentum, MultiCondition
    parameters: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ExitRule(BaseModel):
    """Exit trigger logic schema."""

    name: str
    condition_type: str  # Fixed, SignalExit, StopLoss, TrailingStop, ProfitTarget, VolatilityExit
    parameters: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class PositionSizingRule(BaseModel):
    """Portfolio capital allocation rule schema."""

    name: str
    sizing_type: str  # FixedSize, FixedFractional, VolatilityTarget, Kelly, RiskBudget
    parameters: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class RiskRule(BaseModel):
    """Pre-backtest safety limit schema."""

    name: str
    limit_type: str  # MaxRiskPerTrade, MaxDrawdown, ExposureLimits, SymbolConcentration
    value: float
    parameters: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class StrategyDefinition(BaseModel):
    """Executable trading strategy definition containing rules, sizing, and risk parameters."""

    strategy_id: str
    name: str
    display_name: str
    description: str
    version: str
    entry_rules: List[EntryRule] = Field(default_factory=list)
    exit_rules: List[ExitRule] = Field(default_factory=list)
    sizing_rule: PositionSizingRule
    risk_rules: List[RiskRule] = Field(default_factory=list)
    status: str = "DRAFT"  # DRAFT, VALIDATED, APPROVED, ARCHIVED
    created_time: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class StrategyCandidate(BaseModel):
    """Strategy candidate wrap."""

    candidate_id: str
    strategy: StrategyDefinition
    author: str
    creation_time: datetime = Field(default_factory=datetime.utcnow)
    status: str = "PENDING"

    model_config = ConfigDict(frozen=True)


class StrategyVersion(BaseModel):
    """Version descriptor."""

    strategy_id: str
    semantic_version: str
    commit_hash: str
    author: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class StrategyEvaluation(BaseModel):
    """Results from backtesting evaluation."""

    strategy_id: str
    backtest_id: str
    metrics: Dict[str, float] = Field(default_factory=dict)
    is_approved: bool
    details: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class StrategyPromotion(BaseModel):
    """Strategy promotion audit report."""

    strategy_id: str
    validation_status: str
    approved_by: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class StrategyMetadata(BaseModel):
    """Strategy index metadata tags and parameters."""

    strategy_id: str
    tags: List[str] = Field(default_factory=list)
    target_assets: List[str] = Field(default_factory=list)
    timeframes: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class StrategyLifecycle(BaseModel):
    """Lifecycle details."""

    strategy_id: str
    current_state: str
    updated_time: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class StrategySnapshot(BaseModel):
    """Serialized strategy definition backup."""

    snapshot_id: str
    strategy_id: str
    definition_json: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class StrategyTemplate(BaseModel):
    """Reusable template skeleton."""

    template_id: str
    name: str
    base_entry_rules: List[EntryRule] = Field(default_factory=list)
    base_exit_rules: List[ExitRule] = Field(default_factory=list)
    base_sizing: PositionSizingRule

    model_config = ConfigDict(frozen=True)
