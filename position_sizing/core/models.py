"""Pydantic V2 models for the Position Sizing Engine subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Any

from position_sizing.core.enums import PositionSizingMethod, SizingStatus


class PositionSize(BaseModel):
    """Immutable model representing the computed position parameters."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    quantity: float = Field(..., description="Calculated base currency / token amount.")
    lots: float = Field(..., description="Quantity in standardized contracts or lots.")
    leverage: float = Field(..., description="The computed or required leverage.")
    margin_required: float = Field(..., description="Estimated margin required for this position size.")
    account_risk_percent: float = Field(..., description="Calculated risk percentage relative to total account equity.")
    capital_used: float = Field(..., description="Calculated value of the position size in account currency.")
    stop_distance: float = Field(..., description="The price distance to the stop-loss.")
    take_profit_distance: float = Field(..., description="The price distance to the take-profit.")
    sizing_method: PositionSizingMethod = Field(..., description="The method/algorithm used to determine this size.")
    confidence: float = Field(..., description="Optional scaling multiplier (0.0 to 1.0) applied from upstream.")
    expected_loss: float = Field(default=0.0, description="Expected dollar loss if stop-loss hit.")
    expected_gain: float = Field(default=0.0, description="Expected dollar gain if take-profit hit.")
    reason: str = Field(default="", description="Detailed reason description for the sizing decision.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Calculation timestamp.",
    )

    model_config = ConfigDict(frozen=True)


class PositionSizingResult(BaseModel):
    """Consolidated response containing sizing calculations and validation results."""

    success: bool = Field(..., description="True if position size passed all validation checks.")
    status: SizingStatus = Field(..., description="Status (APPROVED, REJECTED, ADJUSTED).")
    position_size: PositionSize | None = Field(default=None, description="Detailed position parameters if success, else None.")
    reasons: list[str] = Field(default_factory=list, description="Reason descriptions for adjustment/rejection/approval.")
    violations: list[str | Any] = Field(default_factory=list, description="List of specific rule violations (if any).")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Result generation timestamp.",
    )

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="before")
    @classmethod
    def stringify_violations(cls, data: Any) -> Any:
        if isinstance(data, dict) and "violations" in data:
            raw_violations = data["violations"]
            if isinstance(raw_violations, list):
                data["violations"] = [str(v) for v in raw_violations]
        return data


class PositionSizingState(BaseModel):
    """Immutable state holding the active sizing result for a symbol/timeframe."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    result: PositionSizingResult = Field(..., description="Evaluated position sizing result.")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp.",
    )

    model_config = ConfigDict(frozen=True)


class PositionSizingSnapshot(BaseModel):
    """Unified snapshot of position sizing states across multiple timeframes for a symbol."""

    snapshot_id: str = Field(..., description="Unique UUID for this snapshot.")
    symbol: str = Field(..., description="Ticker symbol.")
    timestamp: datetime = Field(..., description="Snapshot timestamp.")
    states: dict[str, PositionSizingState] = Field(
        default_factory=dict,
        description="Timeframe mapped to timeframe-specific PositionSizingState.",
    )

    model_config = ConfigDict(frozen=True)
