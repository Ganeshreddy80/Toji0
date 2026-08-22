"""Pydantic V2 models for the Confluence Engine."""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field

from confluence.core.enums import SetupGrade, RiskFlagType


class SupportingFactor(BaseModel):
    """Immutable model representing a factor contributing positively to confluence."""

    name: str = Field(..., description="Name/label of the factor.")
    category: str = Field(..., description="Category group (e.g. 'TREND', 'STRUCTURE').")
    value: float = Field(..., description="Value or score contribution of the factor.")
    description: str = Field(..., description="Explanation of why this factor was selected.")

    model_config = ConfigDict(frozen=True)


class ConflictingFactor(BaseModel):
    """Immutable model representing a factor conflicting with the setup quality."""

    name: str = Field(..., description="Name/label of the conflicting factor.")
    category: str = Field(..., description="Category group (e.g. 'CORRELATION', 'TREND').")
    penalty: float = Field(..., description="Score penalty deducted.")
    description: str = Field(..., description="Explanation of why this conflict applies.")

    model_config = ConfigDict(frozen=True)


class OpportunityScore(BaseModel):
    """Immutable model for opportunity quality metrics."""

    setup_quality: float = Field(..., ge=0.0, le=100.0, description="Setup quality score [0, 100].")
    execution_quality: float = Field(..., ge=0.0, le=100.0, description="Execution quality score [0, 100].")
    expected_rr: float = Field(..., ge=0.0, description="Expected risk/reward ratio.")
    opportunity_score: float = Field(..., ge=0.0, le=100.0, description="Combined opportunity score [0, 100].")

    model_config = ConfigDict(frozen=True)


class RiskFlag(BaseModel):
    """Immutable model for a single risk flag evaluation."""

    flag_type: RiskFlagType = Field(..., description="Type of risk flag.")
    severity: float = Field(..., ge=0.0, le=1.0, description="Severity level [0, 1].")
    description: str = Field(..., description="Human-readable description of the risk.")
    active: bool = Field(..., description="Whether this risk flag is currently active.")

    model_config = ConfigDict(frozen=True)


class TradeExplanation(BaseModel):
    """Immutable, deterministic trade recommendation explanation."""

    recommendation: str = Field(..., description="Trade recommendation (STRONG_BUY, BUY, HOLD, AVOID, NO_TRADE).")
    reasons: list[str] = Field(default_factory=list, description="Ordered list of supporting reasons.")
    risk_summary: str = Field(..., description="Summary of identified risks.")
    grade_rationale: str = Field(..., description="Explanation of why the grade was assigned.")
    key_factors: list[str] = Field(default_factory=list, description="Top contributing factors.")

    model_config = ConfigDict(frozen=True)


class ConfluenceScore(BaseModel):
    """Immutable model representing the calculated confluence score components and factors."""

    overall_score: float = Field(..., ge=0.0, le=100.0, description="Overall normalized confluence score [0, 100].")
    setup_grade: SetupGrade = Field(..., description="Categorized setup grade (A+, A, B+, B, C, No Trade).")
    trend_score: float = Field(..., ge=0.0, le=100.0, description="Trend component score.")
    structure_score: float = Field(..., ge=0.0, le=100.0, description="Structure component score.")
    liquidity_score: float = Field(..., ge=0.0, le=100.0, description="Liquidity component score.")
    zone_score: float = Field(..., ge=0.0, le=100.0, description="Zone component score.")
    volume_score: float = Field(..., ge=0.0, le=100.0, description="Volume component score.")
    regime_score: float = Field(..., ge=0.0, le=100.0, description="Regime component score.")
    session_score: float = Field(..., ge=0.0, le=100.0, description="Session component score.")
    mtf_score: float = Field(..., ge=0.0, le=100.0, description="MTF component score.")
    correlation_score: float = Field(..., ge=0.0, le=100.0, description="Correlation component score.")
    pattern_score: float = Field(..., ge=0.0, le=100.0, description="Pattern component score.")
    quality_score: float = Field(..., ge=0.0, le=100.0, description="Pattern quality component score.")
    conflict_penalty: float = Field(..., ge=0.0, le=6.0, description="Total conflict penalty deducted [0, 6.0].")
    supporting_factors: list[SupportingFactor] = Field(default_factory=list, description="All positive contributing factors.")
    conflicting_factors: list[ConflictingFactor] = Field(default_factory=list, description="All negative conflicting factors.")

    # Sprint 6: Opportunity, Risk Flags, Explanation
    opportunity: OpportunityScore | None = Field(default=None, description="Opportunity quality metrics.")
    risk_flags: list[RiskFlag] = Field(default_factory=list, description="Active and inactive risk flags.")
    explanation: TradeExplanation | None = Field(default=None, description="Deterministic trade explanation.")

    model_config = ConfigDict(frozen=True)


class ConfluenceState(BaseModel):
    """Immutable confluence evaluation state for a symbol and timeframe."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    score: ConfluenceScore = Field(..., description="Detailed score components.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp.")

    model_config = ConfigDict(frozen=True)


class ConfluenceSnapshot(BaseModel):
    """Unified snapshot of confluence states across multiple timeframes for a symbol."""

    snapshot_id: str = Field(..., description="Unique UUID for this snapshot.")
    symbol: str = Field(..., description="Ticker symbol.")
    timestamp: datetime = Field(..., description="Snapshot timestamp.")
    states: dict[str, ConfluenceState] = Field(
        default_factory=dict,
        description="Timeframe mapped to timeframe-specific ConfluenceState.",
    )

    model_config = ConfigDict(frozen=True)
