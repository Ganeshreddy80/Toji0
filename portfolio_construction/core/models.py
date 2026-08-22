"""Pydantic V2 immutable models for the Portfolio Construction Engine."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from portfolio_construction.core.enums import PortfolioDecision


class PortfolioCandidate(BaseModel):
    """Immutable model representing a strategy signal setup candidate for portfolio inclusion."""

    signal_id: str = Field(..., description="Unique UUID of the generating StrategySignal.")
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Timeframe of the signal.")
    direction: str = Field(..., description="Trade direction (BULLISH, BEARISH).")
    strategy_type: str = Field(..., description="Strategy category.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Normalized signal confidence score [0.0, 1.0].")
    sector: str = Field(default="GENERAL", description="Asset sector/group classification.")
    expected_return: float = Field(default=0.0, description="Estimated expected return metric.")
    volatility: float = Field(default=0.0, description="Estimated historical volatility metric.")

    model_config = ConfigDict(frozen=True)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v: Any) -> float:
        if v is None:
            return 0.0
        val = float(v)
        if val < 0.0:
            raise ValueError("Confidence cannot be negative.")
        if val > 1.0:
            val /= 100.0
        return round(max(0.0, min(1.0, val)), 4)


class PortfolioConstraintConfig(BaseModel):
    """Immutable configuration defining portfolio allocation bounds and risk limits."""

    max_correlation: float = Field(default=0.70, ge=0.0, le=1.0, description="Max allowed pairwise asset correlation.")
    max_weight_per_asset: float = Field(default=0.40, ge=0.0, le=1.0, description="Max allocation weight per asset.")
    min_weight_per_asset: float = Field(default=0.05, ge=0.0, le=1.0, description="Min allocation weight per included asset.")
    max_positions: int = Field(default=10, gt=0, description="Max number of concurrent portfolio positions.")
    max_sector_exposure: float = Field(default=0.50, ge=0.0, le=1.0, description="Max cumulative allocation weight per sector.")
    min_portfolio_confidence: float = Field(default=0.50, ge=0.0, le=1.0, description="Min aggregate confidence to trigger rebalance.")

    model_config = ConfigDict(frozen=True)


class TargetAllocation(BaseModel):
    """Immutable target weight allocation for an individual asset in the constructed portfolio."""

    symbol: str = Field(..., description="Ticker symbol.")
    target_weight: float = Field(..., ge=0.0, le=1.0, description="Normalized portfolio allocation weight [0.0, 1.0].")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Normalized setup confidence [0.0, 1.0].")
    strategy_type: str = Field(..., description="Strategy source identifier.")
    reasoning: str = Field(..., description="Allocation rationale.")

    model_config = ConfigDict(frozen=True)


class TargetPortfolio(BaseModel):
    """Immutable target portfolio decision representing recommended asset allocations."""

    portfolio_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique portfolio decision UUID.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Construction timestamp.")
    decision: PortfolioDecision = Field(default=PortfolioDecision.HOLD, description="Portfolio posture (REBALANCE, HOLD, DELEVERAGE).")
    allocations: Dict[str, TargetAllocation] = Field(default_factory=dict, description="Asset symbol mapped to TargetAllocation.")
    target_weights: Dict[str, float] = Field(default_factory=dict, description="Asset symbol mapped to target weight float.")
    total_weight: float = Field(default=0.0, ge=0.0, le=1.0, description="Sum of target allocation weights.")
    active_positions_count: int = Field(default=0, ge=0, description="Number of allocated assets.")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Aggregate portfolio confidence score.")
    reasoning: str = Field(..., description="Summary explanation of portfolio construction decision.")
    rejected_candidates: List[str] = Field(default_factory=list, description="List of symbols/signals filtered out.")

    model_config = ConfigDict(frozen=True)


class PortfolioConstructionState(BaseModel):
    """Immutable active portfolio state tracking."""

    symbol: str = Field(default="PORTFOLIO", description="Portfolio tracking key.")
    active_portfolio: TargetPortfolio = Field(..., description="Currently active constructed target portfolio.")
    history: List[TargetPortfolio] = Field(default_factory=list, description="Historical list of constructed portfolios.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp.")

    model_config = ConfigDict(frozen=True)


class PortfolioConstructionSnapshot(BaseModel):
    """Unified snapshot of portfolio construction state and correlation matrix."""

    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Snapshot UUID.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Snapshot timestamp.")
    state: PortfolioConstructionState = Field(..., description="Portfolio construction state.")
    correlation_matrix: Dict[str, Dict[str, float]] = Field(default_factory=dict, description="Pairwise correlation matrix.")

    model_config = ConfigDict(frozen=True)
