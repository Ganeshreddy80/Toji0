"""Pydantic V2 models for the Market Intelligence Layer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from market_intelligence.core.enums import (
    HealthState,
    MarketPhase,
    MarketRegime as MarketRegimeEnum,
    ReplayStatus,
    SessionName,
    StructureBias,
    SwingType,
    TrendDirection,
    VolumeExpansionState,
    ZoneType,
)


class SwingPoint(BaseModel):
    """Immutable Swing point (pivot high/low) model."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Candle interval (e.g. 1h).")
    point_type: SwingType = Field(..., description="HIGH or LOW pivot.")
    price: float = Field(..., gt=0.0, description="Pivot price level.")
    timestamp: datetime = Field(..., description="Timestamp of the swing candle.")
    index: int = Field(..., ge=0, description="Absolute index of the swing candle.")

    model_config = ConfigDict(frozen=True)


class TrendState(BaseModel):
    """Immutable Trend classification state."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Candle interval.")
    direction: TrendDirection = Field(..., description="UP, DOWN, or SIDEWAYS.")
    strength: float = Field(..., ge=0.0, le=1.0, description="Trend strength metric (0 to 1).")
    start_time: datetime = Field(..., description="Start of the current trend.")
    end_time: datetime = Field(..., description="End/update timestamp.")

    model_config = ConfigDict(frozen=True)


class LiquidityState(BaseModel):
    """Immutable Liquidity pools state."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Candle interval.")
    buy_side_pools: list[float] = Field(default_factory=list, description="Buy-side price levels.")
    sell_side_pools: list[float] = Field(default_factory=list, description="Sell-side price levels.")
    swept_levels: list[float] = Field(default_factory=list, description="Recently swept price levels.")

    model_config = ConfigDict(frozen=True)


class Zone(BaseModel):
    """Immutable Supply & Demand zone block."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Candle interval.")
    zone_type: ZoneType = Field(..., description="SUPPLY or DEMAND.")
    upper_bound: float = Field(..., gt=0.0, description="Upper price coordinate.")
    lower_bound: float = Field(..., gt=0.0, description="Lower price coordinate.")
    volume_at_creation: float = Field(..., ge=0.0, description="Volume during zone creation.")
    mitigations_count: int = Field(default=0, ge=0, description="Zone touch test counter.")
    is_invalidated: bool = Field(default=False, description="Flag if zone was penetrated.")

    model_config = ConfigDict(frozen=True)


class SessionState(BaseModel):
    """Immutable session tracking state."""

    symbol: str = Field(..., description="Ticker symbol.")
    session_name: SessionName = Field(..., description="Active session name.")
    session_high: float = Field(..., gt=0.0, description="Session high price.")
    session_low: float = Field(..., gt=0.0, description="Session low price.")
    session_open: float | None = Field(default=None, description="Session opening price.")
    session_close: float | None = Field(default=None, description="Session closing price.")
    is_broken: bool = Field(default=False, description="Whether range was breached.")

    model_config = ConfigDict(frozen=True)


class VolumeState(BaseModel):
    """Immutable volume context state."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Candle interval.")
    volume_ma: float = Field(..., ge=0.0, description="Moving average of volume.")
    normalized_volume: float = Field(..., ge=0.0, description="Current volume normalized by MA.")
    expansion_state: VolumeExpansionState = Field(..., description="NORMAL, EXPANSION or CLIMATIC.")
    atr: float = Field(default=0.0, description="Average True Range.")

    model_config = ConfigDict(frozen=True)


class ContextState(BaseModel):
    """Immutable market context classification state."""

    symbol: str = Field(..., description="Ticker symbol.")
    market_phase: MarketPhase = Field(..., description="ACCUMULATION, TRENDING, etc.")
    dominant_bias: StructureBias = Field(..., description="BULLISH, BEARISH or RANGING.")
    key_support: float = Field(..., gt=0.0, description="Primary support level.")
    key_resistance: float = Field(..., gt=0.0, description="Primary resistance level.")
    timestamp: datetime = Field(..., description="Evaluation timestamp.")

    model_config = ConfigDict(frozen=True)


class ConfidenceState(BaseModel):
    """Immutable model confidence state."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(default="1h", description="Candle interval.")
    score: float = Field(..., ge=0.0, le=1.0, description="Calculated confidence score (0 to 1).")
    factors: dict[str, float] = Field(default_factory=dict, description="Factor components breakdown.")
    contribution_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Weighted contribution of each factor to the final score.",
    )
    timestamp: datetime = Field(..., description="Evaluation timestamp.")

    model_config = ConfigDict(frozen=True)


class StoryState(BaseModel):
    """Immutable narrative description block."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(default="1h", description="Candle interval.")
    narrative: str = Field(..., description="Structured narrative summary.")
    sections: dict[str, str] = Field(
        default_factory=dict,
        description="Named sections of the narrative (e.g. 'Current Trend', 'Liquidity').",
    )
    supporting_events: list[str] = Field(default_factory=list, description="List of events driving story.")
    generated_at: datetime = Field(..., description="Story creation timestamp.")

    model_config = ConfigDict(frozen=True)


class StructurePoint(BaseModel):
    """Immutable classified structure point details."""

    swing_point: SwingPoint = Field(..., description="Confirmed swing point details.")
    classification: str = Field(..., description="HH, HL, LH, or LL classification.")

    model_config = ConfigDict(frozen=True)


class BOSRecord(BaseModel):
    """Immutable record of a Break of Structure breakout."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    level_breached: float = Field(..., description="Breached price level coordinate.")
    direction: str = Field(..., description="UP or DOWN breakout direction.")
    break_timestamp: datetime = Field(..., description="Timestamp of the breakout candle.")
    volume_at_break: float = Field(..., description="Volume of the breakout candle.")

    model_config = ConfigDict(frozen=True)


class CHoCHRecord(BaseModel):
    """Immutable record of a Change of Character breakout."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    level_breached: float = Field(..., description="Breached price level coordinate.")
    direction: str = Field(..., description="BULLISH_TO_BEARISH or BEARISH_TO_BULLISH direction.")
    trigger_timestamp: datetime = Field(..., description="Timestamp of the breakout close.")

    model_config = ConfigDict(frozen=True)


class SRLevel(BaseModel):
    """Immutable Support and Resistance horizontal level."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    price: float = Field(..., gt=0.0, description="Horizontal price level.")
    level_type: str = Field(..., description="SUPPORT or RESISTANCE.")
    touch_count: int = Field(default=1, ge=1, description="Number of swing points clustering on this level.")
    strength: float = Field(default=1.0, ge=0.0, description="Weighted strength of the level.")

    model_config = ConfigDict(frozen=True)


class TimeframeAlignment(BaseModel):
    """Immutable timeframe alignment state across multiple timeframes."""

    dominant_trend: TrendDirection = Field(..., description="Dominant trend direction across timeframes.")
    alignment_score: float = Field(..., ge=0.0, le=1.0, description="Trend alignment score (0 to 1).")
    conflict_score: float = Field(..., ge=0.0, le=1.0, description="Trend conflict score (0 to 1).")
    higher_timeframe_confirmation: bool = Field(..., description="True if next higher timeframe matches current trend.")
    timeframe_trends: dict[str, str] = Field(default_factory=dict, description="Trends mapped by timeframe.")

    model_config = ConfigDict(frozen=True)


class MarketContext(BaseModel):
    """Immutable synthesized multi-dimensional market context."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    dominant_trend: TrendDirection = Field(..., description="Dominant trend across timeframes.")
    session: SessionState | None = Field(default=None, description="Active session state.")
    regime: MarketRegimeEnum = Field(..., description="Active market regime classification.")
    alignment: TimeframeAlignment = Field(..., description="Timeframe trend alignment details.")
    liquidity: LiquidityState | None = Field(default=None, description="Active liquidity state.")
    active_zones: list[Zone] = Field(default_factory=list, description="Supply/Demand zones.")
    volume_context: VolumeState | None = Field(default=None, description="Volume state.")
    correlation: dict[str, float] = Field(default_factory=dict, description="Rolling asset correlations.")
    support_resistance: list[SRLevel] = Field(default_factory=list, description="Support & Resistance levels.")
    confidence_inputs: dict[str, float] = Field(default_factory=dict, description="Inputs for confidence calculations.")
    timestamp: datetime = Field(..., description="Synthesized timestamp.")

    model_config = ConfigDict(frozen=True)


class MarketState(BaseModel):
    """Comprehensive state aggregation for a single asset timeframe."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    swings: list[SwingPoint] = Field(default_factory=list, description="Historical swing pivots list.")
    trend: TrendState | None = Field(default=None, description="Active trend state.")
    liquidity: LiquidityState | None = Field(default=None, description="Active liquidity state.")
    zones: list[Zone] = Field(default_factory=list, description="Supply/Demand zones list.")
    session: SessionState | None = Field(default=None, description="Active session state.")
    volume: VolumeState | None = Field(default=None, description="Active volume state.")
    context: ContextState | None = Field(default=None, description="Synthesized context state.")
    confidence: ConfidenceState | None = Field(default=None, description="Confidence metrics.")
    story: StoryState | None = Field(default=None, description="Context narrative.")
    structure_history: list[StructurePoint] = Field(default_factory=list, description="Historical classified swing points.")
    bos_history: list[BOSRecord] = Field(default_factory=list, description="Historical BOS breakout records.")
    choch_history: list[CHoCHRecord] = Field(default_factory=list, description="Historical CHoCH breakout records.")
    sr_levels: list[SRLevel] = Field(default_factory=list, description="Horizontal Support/Resistance levels.")
    market_phase_state: str = Field(default="Unknown", description="Active state machine state.")
    market_context: MarketContext | None = Field(default=None, description="Synthesized Market Context details.")
    
    # New Sprint 5 Analysis fields
    regime_analysis: MarketRegime | None = Field(default=None, description="Market Regime analysis details.")
    trend_analysis: TrendAnalysis | None = Field(default=None, description="Trend analysis details.")
    volatility_analysis: VolatilityAnalysis | None = Field(default=None, description="Volatility analysis details.")
    liquidity_analysis: LiquidityAnalysis | None = Field(default=None, description="Liquidity analysis details.")
    order_flow_analysis: OrderFlowAnalysis | None = Field(default=None, description="Order flow analysis details.")
    volume_profile_analysis: VolumeProfileAnalysis | None = Field(default=None, description="Volume profile analysis details.")
    correlation_analysis: CorrelationAnalysis | None = Field(default=None, description="Correlation analysis details.")
    market_confidence: MarketConfidence | None = Field(default=None, description="Market confidence details.")
    market_intelligence: MarketIntelligence | None = Field(default=None, description="Full market intelligence package.")
    
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class MarketSnapshot(BaseModel):
    """Unified system snapshot containing state for multiple asset timeframes."""

    snapshot_id: str = Field(..., description="Unique UUID for this snapshot.")
    symbol: str = Field(..., description="Ticker symbol.")
    timestamp: datetime = Field(..., description="Snapshot creation timestamp.")
    states: dict[str, MarketState] = Field(
        default_factory=dict,
        description="Timeframe string mapped to timeframe-specific MarketState.",
    )

    model_config = ConfigDict(frozen=True)


class ReplayReport(BaseModel):
    """Immutable report from a deterministic replay verification run."""

    report_id: str = Field(..., description="Unique report identifier.")
    symbol: str = Field(..., description="Ticker symbol.")
    total_candles: int = Field(..., ge=0, description="Number of candles replayed.")
    hash_live: str = Field(..., description="SHA-256 hash of the live state sequence.")
    hash_replay: str = Field(..., description="SHA-256 hash of the replay state sequence.")
    matched: bool = Field(..., description="True if live and replay hashes match.")
    divergence_at: int | None = Field(
        default=None, description="Candle index of first divergence, or None if matched."
    )
    status: ReplayStatus = Field(..., description="Replay verification status.")
    duration_ms: float = Field(..., ge=0.0, description="Replay execution time in milliseconds.")
    timestamp: datetime = Field(..., description="Report generation timestamp.")

    model_config = ConfigDict(frozen=True)


class PerformanceReport(BaseModel):
    """Immutable performance metrics report."""

    report_id: str = Field(..., description="Unique report identifier.")
    symbol: str = Field(default="", description="Ticker symbol (empty for aggregate).")
    mean_latency_ms: float = Field(..., ge=0.0, description="Mean processing latency in ms.")
    p99_latency_ms: float = Field(..., ge=0.0, description="99th percentile latency in ms.")
    events_per_sec: float = Field(..., ge=0.0, description="Events published per second.")
    memory_usage_mb: float = Field(default=0.0, ge=0.0, description="Current memory usage in MB.")
    total_candles: int = Field(..., ge=0, description="Total candles processed.")
    timestamp: datetime = Field(..., description="Report generation timestamp.")

    model_config = ConfigDict(frozen=True)


class HealthReport(BaseModel):
    """Immutable health status report for the MIL subsystem."""

    engine_statuses: dict[str, HealthState] = Field(
        default_factory=dict, description="Health status per engine component."
    )
    dependency_failures: list[str] = Field(
        default_factory=list, description="Names of failed dependencies."
    )
    last_update: datetime = Field(..., description="Timestamp of last successful update.")
    processing_latency_ms: float = Field(default=0.0, ge=0.0, description="Latest processing latency.")
    replay_status: ReplayStatus = Field(
        default=ReplayStatus.PENDING, description="Latest replay verification status."
    )
    overall_status: HealthState = Field(..., description="Aggregate health status.")
    timestamp: datetime = Field(..., description="Report generation timestamp.")

    model_config = ConfigDict(frozen=True)


# ─── Sprint 5 New Domain Models ─────────────────────────────────────────────

class MarketRegime(BaseModel):
    """Pydantic model for Market Regime details."""
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Timeframe.")
    regime: MarketRegimeEnum = Field(..., description="Classified regime enum.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence (0 to 1).")
    trend_strength: float = Field(..., ge=0.0, le=1.0, description="Trend strength (0 to 1).")
    volatility_level: float = Field(..., ge=0.0, description="Volatility level.")
    timestamp: datetime = Field(..., description="Generation timestamp.")

    model_config = ConfigDict(frozen=True)


class TrendAnalysis(BaseModel):
    """Pydantic model for detailed Trend analysis."""
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Timeframe.")
    direction: TrendDirection = Field(..., description="Trend direction UP, DOWN or SIDEWAYS.")
    strength: float = Field(..., ge=0.0, le=1.0, description="Trend strength (0 to 1).")
    duration_bars: int = Field(..., ge=0, description="Trend duration in bars.")
    slope: float = Field(..., description="Slope of the trend line.")
    acceleration: float = Field(..., description="Acceleration of the trend.")
    ema20: float = Field(..., description="EMA 20 price.")
    ema50: float = Field(..., description="EMA 50 price.")
    ema100: float = Field(..., description="EMA 100 price.")
    ema200: float = Field(..., description="EMA 200 price.")
    start_time: datetime = Field(..., description="Trend start timestamp.")
    end_time: datetime = Field(..., description="Trend evaluation end timestamp.")

    model_config = ConfigDict(frozen=True)


class VolatilityAnalysis(BaseModel):
    """Pydantic model for Volatility analysis."""
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Timeframe.")
    atr: float = Field(..., ge=0.0, description="Average True Range.")
    historical_volatility: float = Field(..., ge=0.0, description="Historical Volatility.")
    realized_volatility: float = Field(..., ge=0.0, description="Realized Volatility.")
    bollinger_width: float = Field(..., ge=0.0, description="Bollinger Band width ratio.")
    volatility_percentile: float = Field(..., ge=0.0, le=100.0, description="Volatility Percentile (0 to 100).")
    daily_range: float = Field(..., ge=0.0, description="Daily high-low price range.")
    timestamp: datetime = Field(..., description="Evaluation timestamp.")

    model_config = ConfigDict(frozen=True)


class LiquidityAnalysis(BaseModel):
    """Pydantic model for Liquidity and sweep analysis."""
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Timeframe.")
    bid_ask_spread: float = Field(..., ge=0.0, description="Spread size.")
    depth: float = Field(..., ge=0.0, description="Order book depth volume.")
    market_impact_estimate: float = Field(..., ge=0.0, description="Market impact estimation.")
    slippage_estimate: float = Field(..., ge=0.0, description="Slippage estimation ratio.")
    volume_score: float = Field(..., ge=0.0, le=100.0, description="Liquidity volume score (0 to 100).")
    liquidity_score: float = Field(..., ge=0.0, le=100.0, description="Combined liquidity score (0 to 100).")
    buy_side_pools: list[float] = Field(default_factory=list, description="Buy-side price levels.")
    sell_side_pools: list[float] = Field(default_factory=list, description="Sell-side price levels.")
    swept_levels: list[float] = Field(default_factory=list, description="Recently swept price levels.")
    timestamp: datetime = Field(..., description="Evaluation timestamp.")

    model_config = ConfigDict(frozen=True)


class OrderFlowAnalysis(BaseModel):
    """Pydantic model for Order Flow analysis."""
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Timeframe.")
    trade_delta: float = Field(..., description="Buy minus sell volume delta.")
    buy_volume: float = Field(..., ge=0.0, description="Estimated buy volume.")
    sell_volume: float = Field(..., ge=0.0, description="Estimated sell volume.")
    large_trades: int = Field(..., ge=0, description="Count of large transactions.")
    aggressive_buyers: float = Field(..., ge=0.0, description="Aggressive buying volume.")
    aggressive_sellers: float = Field(..., ge=0.0, description="Aggressive selling volume.")
    order_imbalance: float = Field(..., description="Order book imbalance ratio.")
    timestamp: datetime = Field(..., description="Evaluation timestamp.")

    model_config = ConfigDict(frozen=True)


class VolumeProfileAnalysis(BaseModel):
    """Pydantic model for Volume Profile analysis."""
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Timeframe.")
    poc: float = Field(..., description="Point of Control price.")
    vah: float = Field(..., description="Value Area High price.")
    val: float = Field(..., description="Value Area Low price.")
    high_volume_nodes: list[float] = Field(default_factory=list, description="High Volume Nodes.")
    low_volume_nodes: list[float] = Field(default_factory=list, description="Low Volume Nodes.")
    acceptance_zones: list[tuple[float, float]] = Field(default_factory=list, description="Price acceptance zones.")
    rejection_zones: list[tuple[float, float]] = Field(default_factory=list, description="Price rejection zones.")
    timestamp: datetime = Field(..., description="Evaluation timestamp.")

    model_config = ConfigDict(frozen=True)


class CorrelationAnalysis(BaseModel):
    """Pydantic model for multi-asset correlation tracking."""
    symbol: str = Field(..., description="Base symbol.")
    timeframe: str = Field(..., description="Timeframe.")
    correlations: dict[str, float] = Field(default_factory=dict, description="Rolling correlations.")
    matrix: dict[str, dict[str, float]] = Field(default_factory=dict, description="Correlation matrix.")
    timestamp: datetime = Field(..., description="Evaluation timestamp.")

    model_config = ConfigDict(frozen=True)


class MarketConfidence(BaseModel):
    """Pydantic model for combined Market Confidence outputs."""
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Timeframe.")
    confidence_score: float = Field(..., ge=0.0, le=100.0, description="Confidence score (0 to 100).")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Risk level score (0 to 100).")
    opportunity_score: float = Field(..., ge=0.0, le=100.0, description="Opportunity level score (0 to 100).")
    market_health: str = Field(..., description="Current market health status (e.g. Healthy, Ranging).")
    timestamp: datetime = Field(..., description="Evaluation timestamp.")

    model_config = ConfigDict(frozen=True)


class MarketIntelligence(BaseModel):
    """Pydantic model wrapping the complete MIL analysis bundle."""
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Timeframe.")
    regime: MarketRegime = Field(..., description="Market regime analysis.")
    trend: TrendAnalysis = Field(..., description="Trend analysis.")
    volatility: VolatilityAnalysis = Field(..., description="Volatility analysis.")
    liquidity: LiquidityAnalysis = Field(..., description="Liquidity analysis.")
    order_flow: OrderFlowAnalysis = Field(..., description="Order flow analysis.")
    volume_profile: VolumeProfileAnalysis = Field(..., description="Volume profile analysis.")
    correlation: CorrelationAnalysis = Field(..., description="Correlation analysis.")
    confidence: MarketConfidence = Field(..., description="Market confidence.")
    timestamp: datetime = Field(..., description="Evaluation timestamp.")

    model_config = ConfigDict(frozen=True)


class MarketIntelligenceConfig(BaseModel):
    """Configuration model for Market Intelligence parameters."""
    ema_periods: list[int] = Field(default_factory=lambda: [20, 50, 100, 200], description="EMA periods.")
    atr_period: int = Field(default=14, description="ATR calculation period.")
    adx_threshold: float = Field(default=25.0, description="ADX threshold.")
    correlation_window: int = Field(default=30, description="Correlation window size.")
    volatility_window: int = Field(default=20, description="Volatility window size.")
    confidence_weights: dict[str, float] = Field(default_factory=dict, description="Confidence weights override.")

    model_config = ConfigDict(frozen=True)
