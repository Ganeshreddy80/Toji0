"""Pydantic V2 models for the Trading Context subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field

from market_intelligence.core.models import MarketState
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState
from strategy.core.models import StrategyState, StrategySignal


class ContextMetadata(BaseModel):
    """Metadata detailing creation context, versioning, and event tracking."""

    engine_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Key-value mapping of package versions.",
    )
    replay_hash: str = Field(
        default="",
        description="State sequence hash value for deterministic validation.",
    )
    pipeline_version: str = Field(
        default="1.0.0",
        description="Pipeline execution protocol version.",
    )
    source_events: list[str] = Field(
        default_factory=list,
        description="List of raw event types that contributed to this state.",
    )
    creation_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the context was constructed.",
    )

    model_config = ConfigDict(frozen=True)


class TradingContext(BaseModel):
    """Unified, immutable data contract holding complete platform state for a symbol's timeframe."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    market_state: MarketState = Field(..., description="Market Intelligence Layer state.")
    pattern_state: PatternState | None = Field(default=None, description="Price Action Engine pattern state.")
    confluence_state: ConfluenceState | None = Field(default=None, description="Confluence Engine scoring state.")
    strategy_state: StrategyState | None = Field(default=None, description="Strategy Engine active state.")
    strategy_signal: StrategySignal | None = Field(default=None, description="Latest strategy signal generated.")
    metadata: ContextMetadata = Field(default_factory=ContextMetadata, description="Versioning and tracking metadata.")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Generation timestamp."
    )
    replay_id: str = Field(default="", description="Unique identifier for replaying execution runs.")
    version: str = Field(default="1.0.0", description="Trading Context contract schema version.")

    model_config = ConfigDict(frozen=True)


class TradingContextSnapshot(BaseModel):
    """Unified snapshot of trading contexts across multiple timeframes for a single symbol."""

    snapshot_id: str = Field(..., description="Unique UUID for this snapshot.")
    symbol: str = Field(..., description="Ticker symbol.")
    timestamp: datetime = Field(..., description="Snapshot timestamp.")
    states: dict[str, TradingContext] = Field(
        default_factory=dict,
        description="Timeframe mapped to timeframe-specific TradingContext.",
    )

    model_config = ConfigDict(frozen=True)
