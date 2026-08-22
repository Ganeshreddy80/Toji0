"""Pydantic V2 models for the Strategy Engine."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator

from price_action.core.enums import PatternDirection
from strategy.core.enums import SignalLifecycleState, StrategyDecision, StrategyType


class StrategySignal(BaseModel):
    """Immutable model representing a standardized strategy setup detection signal."""

    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique UUID for the signal.")
    strategy_id: str = Field(default="strat_default", description="Identifier of the specific strategy module instance.")
    strategy_version: str = Field(default="1.0.0", description="Version string of the generating strategy module.")
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    direction: PatternDirection = Field(..., description="Trade direction (BULLISH, BEARISH).")
    strategy_type: StrategyType = Field(..., description="Strategy category.")
    decision: StrategyDecision = Field(default=StrategyDecision.WAIT, description="Strategy execution decision.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Normalized strategy confidence score [0.0, 1.0].")
    confluence_score: float = Field(..., ge=0.0, le=100.0, description="Confluence score from CE [0, 100].")
    market_regime: str = Field(default="UNKNOWN", description="Market regime classification at signal generation.")
    reasoning: str = Field(..., description="Text rationale for generating the signal.")
    lifecycle_state: SignalLifecycleState = Field(
        default=SignalLifecycleState.NEW, description="Current signal lifecycle state."
    )
    supporting_factors: list[str] = Field(default_factory=list, description="Positive structural setup drivers.")
    conflicting_factors: list[str] = Field(default_factory=list, description="Negative structural setup conflicts.")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of signal generation.",
    )
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Initial detection timestamp.",
    )

    model_config = ConfigDict(frozen=True)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v: Any) -> float:
        """Ensure confidence score is strictly normalized to [0.0, 1.0]."""
        if v is None:
            return 0.0
        val = float(v)
        if val < 0.0:
            raise ValueError("Confidence score cannot be negative.")
        if val > 1.0:
            val /= 100.0
        return round(max(0.0, min(1.0, val)), 4)


class StrategyState(BaseModel):
    """Immutable active setup state tracking for a symbol's timeframe."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    active_strategy: StrategyType | None = Field(default=None, description="Currently active strategy type.")
    latest_signal: StrategySignal | None = Field(default=None, description="Most recently triggered signal details.")
    historical_strategies: list[StrategySignal] = Field(
        default_factory=list,
        description="Historical list of triggered signals on this timeframe.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last state update timestamp.",
    )

    model_config = ConfigDict(frozen=True)


class StrategySnapshot(BaseModel):
    """Unified snapshot of strategy states across multiple timeframes for a symbol."""

    snapshot_id: str = Field(..., description="Unique UUID for this snapshot.")
    symbol: str = Field(..., description="Ticker symbol.")
    timestamp: datetime = Field(..., description="Snapshot timestamp.")
    states: dict[str, StrategyState] = Field(
        default_factory=dict,
        description="Timeframe mapped to timeframe-specific StrategyState.",
    )

    model_config = ConfigDict(frozen=True)
