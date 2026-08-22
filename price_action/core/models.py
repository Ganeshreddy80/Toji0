"""Pydantic V2 models for the Price Action Engine."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from price_action.core.enums import (
    DivergenceType,
    LiquidityType,
    MarketRegimeType,
    MarketStructureType,
    PatternDirection,
    PatternStatus,
    PatternType,
    SwingType,
    TrendDirection,
    ZoneType,
)
from market_intelligence.core.models import (
    MarketState,
    SwingPoint,
    TrendState,
    VolumeState,
    LiquidityState,
    Zone,
    SRLevel,
    SessionState,
)


class PatternQuality(BaseModel):
    """Immutable model representing the quality assessment of a chart pattern."""

    overall_score: float = Field(..., ge=0.0, le=100.0, description="Overall quality score [0, 100].")
    geometry_score: float = Field(..., ge=0.0, le=100.0, description="Geometry score [0, 100].")
    symmetry_score: float = Field(..., ge=0.0, le=100.0, description="Symmetry score [0, 100].")
    breakout_score: float = Field(..., ge=0.0, le=100.0, description="Breakout score [0, 100].")
    regression_score: float = Field(..., ge=0.0, le=100.0, description="Regression score [0, 100].")
    touch_score: float = Field(..., ge=0.0, le=100.0, description="Touch score [0, 100].")
    volume_score: float = Field(..., ge=0.0, le=100.0, description="Volume score [0, 100].")
    volatility_score: float = Field(..., ge=0.0, le=100.0, description="Volatility score [0, 100].")
    age_score: float = Field(..., ge=0.0, le=100.0, description="Age score [0, 100].")
    completion_score: float = Field(..., ge=0.0, le=100.0, description="Completion score [0, 100].")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Confidence score [0, 100].")
    evaluated_at: datetime = Field(..., description="Timestamp of the evaluation.")
    explanation: str = Field(..., description="Details and explanation of the quality assessment.")

    model_config = ConfigDict(frozen=True)


class PatternPoint(BaseModel):
    """Immutable model representing a key anchor point of a price action pattern."""

    price: float = Field(..., gt=0.0, description="Price level of the anchor point.")
    timestamp: datetime = Field(..., description="Timestamp of the anchor point.")
    index: int = Field(..., ge=0, description="Absolute index of the anchor point candle.")
    point_label: str = Field(..., description="Structural label (e.g. 'A', 'Head', 'Shoulder').")

    model_config = ConfigDict(frozen=True)


class Trendline(BaseModel):
    """Immutable model representing a boundary trendline in a pattern."""

    start_point: PatternPoint = Field(..., description="Start coordinate of the trendline.")
    end_point: PatternPoint = Field(..., description="End coordinate of the trendline.")
    slope: float = Field(..., description="Calculated slope of the trendline.")
    intercept: float = Field(..., description="Calculated intercept of the trendline.")

    model_config = ConfigDict(frozen=True)


class PatternCandidate(BaseModel):
    """Immutable model representing a candidate pattern in formation."""

    candidate_id: str = Field(..., description="Unique UUID string for the candidate.")
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Timeframe interval.")
    pattern_type: PatternType = Field(..., description="Price action pattern category.")
    direction: PatternDirection = Field(..., description="Expected directional bias.")
    points: list[PatternPoint] = Field(default_factory=list, description="Anchor points detected.")
    trendlines: list[Trendline] = Field(default_factory=list, description="Pattern boundaries.")
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence fit score.")
    detected_at: datetime = Field(..., description="Initial detection timestamp.")
    metadata: PatternMetadata | None = Field(default=None, description="Detection metadata and scores.")
    quality: PatternQuality | None = Field(default=None, description="Pattern quality assessment.")

    model_config = ConfigDict(frozen=True)


class PatternMatch(BaseModel):
    """Immutable model representing a validated/confirmed price action pattern."""

    match_id: str = Field(..., description="Unique UUID string for the pattern match.")
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Timeframe interval.")
    pattern_type: PatternType = Field(..., description="Price action pattern category.")
    direction: PatternDirection = Field(..., description="Directional bias of the pattern.")
    status: PatternStatus = Field(..., description="Current status (CONFIRMED, COMPLETED, etc.).")
    points: list[PatternPoint] = Field(default_factory=list, description="Anchor points of the pattern.")
    trendlines: list[Trendline] = Field(default_factory=list, description="Pattern boundaries.")
    fit_score: float = Field(..., ge=0.0, le=1.0, description="Fit confidence score.")
    confirmed_at: datetime = Field(..., description="Timestamp when confirmed.")
    completed_at: datetime | None = Field(default=None, description="Timestamp when completed.")
    invalidated_at: datetime | None = Field(default=None, description="Timestamp when invalidated.")
    metadata: PatternMetadata | None = Field(default=None, description="Detection metadata and scores.")
    quality: PatternQuality | None = Field(default=None, description="Pattern quality assessment.")

    model_config = ConfigDict(frozen=True)


class PatternState(BaseModel):
    """Immutable state aggregation of price action patterns for a symbol's timeframe."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    active_patterns: list[PatternMatch] = Field(default_factory=list, description="Currently active confirmed patterns.")
    candidate_patterns: list[PatternCandidate] = Field(default_factory=list, description="Candidate patterns in formation.")
    historical_patterns: list[PatternMatch] = Field(default_factory=list, description="Completed or invalidated patterns.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp.")

    model_config = ConfigDict(frozen=True)


class PatternSnapshot(BaseModel):
    """Unified snapshot of pattern states across multiple timeframes for a symbol."""

    snapshot_id: str = Field(..., description="Unique UUID for this snapshot.")
    symbol: str = Field(..., description="Ticker symbol.")
    timestamp: datetime = Field(..., description="Snapshot timestamp.")
    states: dict[str, PatternState] = Field(
        default_factory=dict,
        description="Timeframe mapped to timeframe-specific PatternState.",
    )

    model_config = ConfigDict(frozen=True)


class PatternMetadata(BaseModel):
    """Audit metadata tracking execution details."""

    source_engine: str = Field(..., description="Identification of the executing detector.")
    version: str = Field(..., description="Version of the detector logic.")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Configuration parameters used.")
    quality_score: float | None = Field(default=None, description="Overall quality score [0, 1].")
    geometry_score: float | None = Field(default=None, description="Geometry conformity score.")
    symmetry_score: float | None = Field(default=None, description="Symmetry/balance score.")
    touch_count: int | None = Field(default=None, description="Number of touches/tests of levels.")
    regression_fit: float | None = Field(default=None, description="R-squared line or curve fit score.")
    volume_confirmation: float | None = Field(default=None, description="Volume confirmation ratio/score.")
    atr_normalization: float | None = Field(default=None, description="ATR-normalized size score.")

    model_config = ConfigDict(frozen=True)


class PatternStatistics(BaseModel):
    """Running performance and classification metrics of patterns."""

    symbol: str = Field(..., description="Ticker symbol.")
    total_detected: int = Field(..., ge=0, description="Total count of patterns detected.")
    by_type: dict[str, int] = Field(default_factory=dict, description="Counts mapped by PatternType.")
    by_status: dict[str, int] = Field(default_factory=dict, description="Counts mapped by PatternStatus.")
    win_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Completed vs invalidated ratio.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last statistical update.")

    model_config = ConfigDict(frozen=True)


class DetectorContext(BaseModel):
    """Context object carrying all inputs needed by pattern detectors."""

    market_state: MarketState = Field(..., description="The source MIL MarketState.")
    atr: float = Field(..., description="Average True Range.")
    swings: list[SwingPoint] = Field(..., description="Confirmed swing points.")
    trend: TrendState | None = Field(default=None, description="Active trend state.")
    volume_state: VolumeState | None = Field(default=None, description="Active volume state.")
    liquidity_state: LiquidityState | None = Field(default=None, description="Active liquidity state.")
    zones: list[Zone] = Field(default_factory=list, description="Supply/Demand zones.")
    sr_levels: list[SRLevel] = Field(default_factory=list, description="Support & Resistance levels.")
    session: SessionState | None = Field(default=None, description="Active session state.")
    timeframe: str = Field(..., description="Target timeframe.")
    current_candle: Any | None = Field(default=None, description="Current raw candle, if available.")
    recent_history: list[Any] = Field(default_factory=list, description="Recent candle history, if available.")

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    @classmethod
    def from_market_state(
        cls,
        market_state: MarketState,
        current_candle: Any | None = None,
        recent_history: list[Any] | None = None,
    ) -> DetectorContext:
        """Construct DetectorContext from a MarketState."""
        atr = 0.0
        if market_state.volume and hasattr(market_state.volume, "atr") and market_state.volume.atr is not None:
            atr = market_state.volume.atr

        if atr <= 0.0:
            # Fallback calculation if volume state doesn't have atr yet
            recent_swings = sorted(market_state.swings[-6:], key=lambda s: s.index)
            if recent_swings:
                atr = (sum(s.price for s in recent_swings) / len(recent_swings)) * 0.01

        return cls(
            market_state=market_state,
            atr=atr,
            swings=market_state.swings,
            trend=market_state.trend,
            volume_state=market_state.volume,
            liquidity_state=market_state.liquidity,
            zones=market_state.zones,
            sr_levels=market_state.sr_levels,
            session=market_state.session,
            timeframe=market_state.timeframe,
            current_candle=current_candle,
            recent_history=recent_history or [],
        )


# =============================================================================
# Sprint 5 Institutional Price Action Models (Immutable Pydantic V2)
# =============================================================================

class PriceActionBar(BaseModel):
    """Immutable representation of an OHLCV market data bar."""

    timestamp: datetime = Field(..., description="Bar opening timestamp.")
    open: float = Field(..., gt=0.0, description="Open price.")
    high: float = Field(..., gt=0.0, description="High price.")
    low: float = Field(..., gt=0.0, description="Low price.")
    close: float = Field(..., gt=0.0, description="Close price.")
    volume: float = Field(default=0.0, ge=0.0, description="Volume.")
    index: int = Field(default=0, ge=0, description="Sequence index.")

    model_config = ConfigDict(frozen=True)


class PriceActionSwing(BaseModel):
    """Immutable swing pivot point representation."""

    swing_type: SwingType = Field(..., description="SWING_HIGH or SWING_LOW.")
    price: float = Field(..., gt=0.0, description="Pivot price level.")
    timestamp: datetime = Field(..., description="Timestamp of pivot bar.")
    index: int = Field(..., ge=0, description="Bar index.")
    strength: int = Field(default=2, ge=1, description="Pivot strength (left/right lookback).")

    model_config = ConfigDict(frozen=True)


class MarketStructureState(BaseModel):
    """Immutable market structure state (BOS, CHOCH, market trend bias)."""

    trend_bias: TrendDirection = Field(default=TrendDirection.SIDEWAYS, description="Structural bias.")
    last_structure_type: MarketStructureType | None = Field(default=None, description="Last detected structure event.")
    last_bos_price: float | None = Field(default=None, description="Price of last Break of Structure.")
    last_choch_price: float | None = Field(default=None, description="Price of last Change of Character.")
    recent_swings: list[PriceActionSwing] = Field(default_factory=list, description="Recent swing points.")

    model_config = ConfigDict(frozen=True)


class TrendMetrics(BaseModel):
    """Immutable trend engine metrics."""

    direction: TrendDirection = Field(default=TrendDirection.SIDEWAYS, description="Trend direction.")
    strength: float = Field(default=0.0, ge=0.0, le=1.0, description="Trend strength [0.0, 1.0].")
    fast_ma: float = Field(default=0.0, description="Fast moving average price.")
    slow_ma: float = Field(default=0.0, description="Slow moving average price.")
    is_aligned: bool = Field(default=False, description="True if price and MAs are strictly aligned.")

    model_config = ConfigDict(frozen=True)


class VolatilityMetrics(BaseModel):
    """Immutable volatility engine metrics."""

    atr: float = Field(default=0.0, ge=0.0, description="Average True Range.")
    atr_percent: float = Field(default=0.0, ge=0.0, description="ATR as percentage of current price.")
    bb_upper: float = Field(default=0.0, description="Bollinger Band upper.")
    bb_lower: float = Field(default=0.0, description="Bollinger Band lower.")
    bb_middle: float = Field(default=0.0, description="Bollinger Band middle (SMA).")
    bb_bandwidth: float = Field(default=0.0, ge=0.0, description="Bollinger Band width ratio.")
    is_squeeze: bool = Field(default=False, description="True if volatility is in a squeeze/compression phase.")

    model_config = ConfigDict(frozen=True)


class MomentumMetrics(BaseModel):
    """Immutable momentum engine metrics."""

    rsi: float = Field(default=50.0, ge=0.0, le=100.0, description="Relative Strength Index.")
    macd: float = Field(default=0.0, description="MACD line.")
    macd_signal: float = Field(default=0.0, description="MACD signal line.")
    macd_histogram: float = Field(default=0.0, description="MACD histogram.")
    divergence: DivergenceType = Field(default=DivergenceType.NONE, description="Momentum divergence classification.")

    model_config = ConfigDict(frozen=True)


class LiquidityPool(BaseModel):
    """Immutable liquidity pool model (BSL/SSL)."""

    pool_id: str = Field(..., description="Unique liquidity pool ID.")
    liquidity_type: LiquidityType = Field(..., description="Buy-Side (BSL) or Sell-Side (SSL).")
    price_level: float = Field(..., gt=0.0, description="Price level of liquidity pool.")
    touches: int = Field(default=1, ge=1, description="Number of touches/tests.")
    is_swept: bool = Field(default=False, description="True if liquidity has been swept/grabbed.")
    swept_at: datetime | None = Field(default=None, description="Sweep timestamp if swept.")

    model_config = ConfigDict(frozen=True)


class FairValueGap(BaseModel):
    """Immutable Fair Value Gap (FVG) model."""

    fvg_id: str = Field(..., description="Unique FVG ID.")
    direction: PatternDirection = Field(..., description="BULLISH or BEARISH imbalance.")
    top: float = Field(..., gt=0.0, description="Top price boundary of FVG.")
    bottom: float = Field(..., gt=0.0, description="Bottom price boundary of FVG.")
    midpoint: float = Field(..., gt=0.0, description="50% midpoint of FVG (Consequent Encroachment).")
    created_at: datetime = Field(..., description="Creation timestamp.")
    is_mitigated: bool = Field(default=False, description="True if price has filled/mitigated FVG.")
    mitigated_at: datetime | None = Field(default=None, description="Mitigation timestamp.")

    model_config = ConfigDict(frozen=True)


class OrderBlock(BaseModel):
    """Immutable institutional Order Block model."""

    ob_id: str = Field(..., description="Unique Order Block ID.")
    direction: PatternDirection = Field(..., description="BULLISH or BEARISH Order Block.")
    top: float = Field(..., gt=0.0, description="Top price boundary.")
    bottom: float = Field(..., gt=0.0, description="Bottom price boundary.")
    high: float = Field(..., gt=0.0, description="High of OB candle.")
    low: float = Field(..., gt=0.0, description="Low of OB candle.")
    volume_surge: float = Field(default=1.0, ge=0.0, description="Volume surge ratio of expansion move.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    is_mitigated: bool = Field(default=False, description="True if price has tested/mitigated OB.")

    model_config = ConfigDict(frozen=True)


class PremiumDiscountState(BaseModel):
    """Immutable Premium / Discount dealing range state."""

    swing_high: float = Field(..., gt=0.0, description="Dealing range swing high.")
    swing_low: float = Field(..., gt=0.0, description="Dealing range swing low.")
    equilibrium: float = Field(..., gt=0.0, description="50% equilibrium level.")
    discount_upper: float = Field(..., gt=0.0, description="50% boundary for discount.")
    premium_lower: float = Field(..., gt=0.0, description="50% boundary for premium.")
    deep_discount_upper: float = Field(..., gt=0.0, description="25% boundary for deep discount.")
    deep_premium_lower: float = Field(..., gt=0.0, description="75% boundary for deep premium.")
    current_zone: ZoneType = Field(default=ZoneType.EQUILIBRIUM, description="Current price zone classification.")

    model_config = ConfigDict(frozen=True)


class MarketRegimeState(BaseModel):
    """Immutable macro market regime classification state."""

    regime: MarketRegimeType = Field(default=MarketRegimeType.RANGING, description="Active market regime.")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Regime classification confidence score.")
    explanation: str = Field(default="Default ranging regime.", description="Rationale for regime classification.")

    model_config = ConfigDict(frozen=True)


class TimeframePriceActionSnapshot(BaseModel):
    """Immutable single-timeframe price action analysis snapshot."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Timeframe string (e.g. '1h').")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Snapshot timestamp.")
    swings: list[PriceActionSwing] = Field(default_factory=list, description="Detected swings.")
    market_structure: MarketStructureState = Field(default_factory=MarketStructureState, description="Market structure state.")
    trend: TrendMetrics = Field(default_factory=TrendMetrics, description="Trend metrics.")
    volatility: VolatilityMetrics = Field(default_factory=VolatilityMetrics, description="Volatility metrics.")
    momentum: MomentumMetrics = Field(default_factory=MomentumMetrics, description="Momentum metrics.")
    liquidity_pools: list[LiquidityPool] = Field(default_factory=list, description="Active liquidity pools.")
    fvgs: list[FairValueGap] = Field(default_factory=list, description="Fair Value Gaps.")
    order_blocks: list[OrderBlock] = Field(default_factory=list, description="Order Blocks.")
    premium_discount: PremiumDiscountState | None = Field(default=None, description="Premium/Discount state.")
    regime: MarketRegimeState = Field(default_factory=MarketRegimeState, description="Market regime state.")

    model_config = ConfigDict(frozen=True)


class MultiTimeframePriceActionSnapshot(BaseModel):
    """Immutable aggregated multi-timeframe price action snapshot."""

    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Snapshot UUID.")
    symbol: str = Field(..., description="Ticker symbol.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Snapshot timestamp.")
    timeframe_snapshots: dict[str, TimeframePriceActionSnapshot] = Field(
        default_factory=dict, description="Timeframe string mapped to TimeframePriceActionSnapshot."
    )
    primary_regime: MarketRegimeType = Field(default=MarketRegimeType.RANGING, description="Primary macro regime.")
    primary_trend: TrendDirection = Field(default=TrendDirection.SIDEWAYS, description="Primary macro trend.")
    confluence_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Multi-timeframe confluence score.")

    model_config = ConfigDict(frozen=True)


class PriceActionConfig(BaseModel):
    """Immutable configuration parameters for Price Action detectors and engines."""

    swing_lookback: int = Field(default=3, ge=1, description="Left/right bar lookback for swing detection.")
    fast_ma_period: int = Field(default=20, ge=1, description="Fast MA period.")
    slow_ma_period: int = Field(default=50, ge=1, description="Slow MA period.")
    atr_period: int = Field(default=14, ge=1, description="ATR calculation period.")
    rsi_period: int = Field(default=14, ge=1, description="RSI period.")
    macd_fast: int = Field(default=12, ge=1, description="MACD fast period.")
    macd_slow: int = Field(default=26, ge=1, description="MACD slow period.")
    macd_signal: int = Field(default=9, ge=1, description="MACD signal period.")
    bb_period: int = Field(default=20, ge=1, description="Bollinger Band period.")
    bb_std_dev: float = Field(default=2.0, gt=0.0, description="Bollinger Band standard deviation multiplier.")
    fvg_min_gap_pct: float = Field(default=0.001, ge=0.0, description="Min imbalance gap percentage.")
    ob_volume_surge_mult: float = Field(default=1.2, ge=0.0, description="Min volume multiplier for OB detection.")
    liquidity_tolerance_pct: float = Field(default=0.002, ge=0.0, description="Price tolerance for equal highs/lows.")

    model_config = ConfigDict(frozen=True)


class PriceActionFeatures(BaseModel):
    """Immutable derived feature dictionary container for Strategy Engine consumption."""

    feature_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Feature record UUID.")
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Timeframe.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Generation timestamp.")
    features: dict[str, float | str | bool] = Field(default_factory=dict, description="Feature dictionary.")

    model_config = ConfigDict(frozen=True)


