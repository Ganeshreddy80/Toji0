"""Unit and integration tests for Strategy rules, SetupValidator, and StrategySelector."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import (
    TrendDirection,
    ZoneType,
    SessionName,
    MarketRegime,
    VolumeExpansionState,
    SwingType,
)
from market_intelligence.core.models import (
    MarketState,
    TrendState,
    Zone,
    SessionState,
    VolumeState,
    ContextState,
    MarketContext,
    TimeframeAlignment,
    SwingPoint,
    BOSRecord,
    CHoCHRecord,
    SRLevel,
)
from price_action.core.enums import (
    PatternDirection,
    PatternStatus,
    PatternType,
)
from price_action.core.models import (
    PatternState,
    PatternMatch,
    PatternCandidate,
    PatternPoint,
    PatternQuality,
)
from confluence.core.enums import SetupGrade
from confluence.core.models import (
    ConfluenceState,
    ConfluenceScore,
)
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.models import StrategySignal
from strategy.analysis.setup_validator import SetupValidator
from strategy.analysis.strategy_selector import StrategySelector
from strategy.analysis.strategy_engine import StrategyEngine
from strategy.analysis.trend_strategy import TrendFollowingStrategy
from strategy.analysis.reversal_strategy import ReversalStrategy
from strategy.analysis.breakout_strategy import BreakoutStrategy
from strategy.analysis.continuation_strategy import ContinuationStrategy
from strategy.analysis.range_strategy import RangeStrategy
from strategy.analysis.mean_reversion_strategy import MeanReversionStrategy
from strategy.analysis.momentum_strategy import MomentumStrategy


class MockLiquidity:
    """Mock liquidity state class with dynamic attribute injection."""
    def __init__(self, swept_low: bool = False, swept_high: bool = False):
        self.swept_low = swept_low
        self.swept_high = swept_high
        self.buy_side_pools = []
        self.sell_side_pools = []
        self.swept_levels = []


@pytest.fixture
def base_context() -> tuple[MarketState, PatternState, ConfluenceState]:
    """Provide baseline MarketState, PatternState, and ConfluenceState."""
    dt = datetime.now(timezone.utc)
    
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=dt,
        market_phase_state="Unknown",
    )
    
    pattern_state = PatternState(
        symbol="BTCUSDT",
        timeframe="1h",
        active_patterns=[],
        candidate_patterns=[],
        updated_at=dt,
    )
    
    confluence_score = ConfluenceScore(
        overall_score=75.0,
        setup_grade=SetupGrade.B,
        trend_score=70.0,
        structure_score=70.0,
        liquidity_score=70.0,
        zone_score=70.0,
        volume_score=70.0,
        regime_score=70.0,
        session_score=70.0,
        mtf_score=70.0,
        white_noise_penalty=0.0,
        correlation_score=70.0,
        pattern_score=70.0,
        quality_score=70.0,
        conflict_penalty=0.0,
        supporting_factors=[],
        conflicting_factors=[],
    )
    
    confluence_state = ConfluenceState(
        symbol="BTCUSDT",
        timeframe="1h",
        score=confluence_score,
        updated_at=dt,
    )
    
    return market_state, pattern_state, confluence_state


def create_pattern_quality(score: float = 80.0) -> PatternQuality:
    """Helper to create a fully validated PatternQuality model."""
    return PatternQuality(
        overall_score=score,
        geometry_score=score,
        symmetry_score=score,
        breakout_score=score,
        regression_score=score,
        touch_score=score,
        volume_score=score,
        volatility_score=score,
        age_score=score,
        completion_score=score,
        confidence=score,
        evaluated_at=datetime.now(timezone.utc),
        explanation="Test quality",
    )


def test_setup_validator(base_context):
    """Test SetupValidator logic."""
    market_state, _, confluence_state = base_context
    
    # Happy path
    assert SetupValidator.is_valid_context(market_state, confluence_state) is True

    # Low Confluence Score
    low_score = confluence_state.score.model_copy(update={"overall_score": 45.0})
    low_confluence = confluence_state.model_copy(update={"score": low_score})
    assert SetupValidator.is_valid_context(market_state, low_confluence) is False

    # High conflict penalty
    high_conflict_score = confluence_state.score.model_copy(update={"conflict_penalty": 5.5})
    high_conflict_confluence = confluence_state.model_copy(update={"score": high_conflict_score})
    assert SetupValidator.is_valid_context(market_state, high_conflict_confluence) is False


def test_trend_following_strategy(base_context):
    """Test TrendFollowingStrategy evaluate logic."""
    market_state, pattern_state, confluence_state = base_context
    strat = TrendFollowingStrategy()

    # Evaluates to None with default sideways trend and no BOS
    assert strat.evaluate(market_state, pattern_state, confluence_state) is None

    # Set up Trend Direction UP and matching BOS
    dt = datetime.now(timezone.utc)
    trend = TrendState(
        symbol="BTCUSDT",
        timeframe="1h",
        direction=TrendDirection.UP,
        strength=0.85,
        start_time=dt,
        end_time=dt,
    )
    bos = BOSRecord(
        symbol="BTCUSDT",
        timeframe="1h",
        level_breached=100.0,
        direction="UP",
        break_timestamp=dt,
        volume_at_break=1000.0,
    )
    market_up = market_state.model_copy(update={"trend": trend, "bos_history": [bos]})

    # Evaluate Trend Following buy signal
    signal = strat.evaluate(market_up, pattern_state, confluence_state)
    assert signal is not None
    assert signal.decision == StrategyDecision.BUY
    assert signal.strategy_type == StrategyType.TREND_FOLLOWING
    assert signal.direction == PatternDirection.BULLISH
    assert signal.confidence > 0.50


def test_reversal_strategy(base_context):
    """Test ReversalStrategy evaluate logic."""
    market_state, pattern_state, confluence_state = base_context
    strat = ReversalStrategy(confluence_min=75.0)

    # Empty context triggers None
    assert strat.evaluate(market_state, pattern_state, confluence_state) is None

    dt = datetime.now(timezone.utc)
    choch = CHoCHRecord(
        symbol="BTCUSDT",
        timeframe="1h",
        level_breached=95.0,
        direction="BEARISH_TO_BULLISH",
        trigger_timestamp=dt,
    )
    liquidity = MockLiquidity(swept_low=True)
    market_rev = market_state.model_copy(update={"choch_history": [choch], "liquidity": liquidity})

    quality = create_pattern_quality(85.0)
    pattern = PatternMatch(
        match_id="pat-rev-1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_BOTTOM,
        direction=PatternDirection.BULLISH,
        status=PatternStatus.CONFIRMED,
        points=[],
        trendlines=[],
        fit_score=0.9,
        confirmed_at=dt,
        quality=quality,
    )
    pattern_rev = pattern_state.model_copy(update={"active_patterns": [pattern]})

    # Evaluate Reversal buy signal
    signal = strat.evaluate(market_rev, pattern_rev, confluence_state)
    assert signal is not None
    assert signal.decision == StrategyDecision.BUY
    assert signal.strategy_type == StrategyType.REVERSAL
    assert signal.confidence == 0.78  # Normalized (75.0 * 0.7) + (85.0 * 0.3) = 78.0 -> 0.78


def test_breakout_strategy(base_context):
    """Test BreakoutStrategy evaluate logic."""
    market_state, pattern_state, confluence_state = base_context
    strat = BreakoutStrategy(rvol_min=1.5, confluence_min=70.0)

    # Empty context triggers None
    assert strat.evaluate(market_state, pattern_state, confluence_state) is None

    # Set up High relative volume
    dt = datetime.now(timezone.utc)
    volume = VolumeState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume_ma=100.0,
        relative_volume=1.8,
        normalized_volume=1.8,
        expansion_state=VolumeExpansionState.EXPANSION,
        volume_trend="UP",
        buying_pressure=0.6,
        selling_pressure=0.4,
        updated_at=dt,
    )
    bos = BOSRecord(
        symbol="BTCUSDT",
        timeframe="1h",
        level_breached=105.0,
        direction="UP",
        break_timestamp=dt,
        volume_at_break=1000.0,
    )
    market_bo = market_state.model_copy(update={"volume": volume, "bos_history": [bos]})

    quality = create_pattern_quality(90.0)
    pattern = PatternMatch(
        match_id="pat-bo-1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.ASC_TRIANGLE,
        direction=PatternDirection.BULLISH,
        status=PatternStatus.CONFIRMED,
        points=[],
        trendlines=[],
        fit_score=0.95,
        confirmed_at=dt,
        quality=quality,
    )
    pattern_bo = pattern_state.model_copy(update={"active_patterns": [pattern]})

    # Evaluate breakout buy signal
    signal = strat.evaluate(market_bo, pattern_bo, confluence_state)
    assert signal is not None
    assert signal.decision == StrategyDecision.BUY
    assert signal.strategy_type == StrategyType.BREAKOUT
    assert signal.confidence > 0.50


def test_continuation_strategy(base_context):
    """Test ContinuationStrategy evaluate logic."""
    market_state, pattern_state, confluence_state = base_context
    strat = ContinuationStrategy(confluence_min=70.0)

    assert strat.evaluate(market_state, pattern_state, confluence_state) is None

    dt = datetime.now(timezone.utc)
    trend = TrendState(
        symbol="BTCUSDT",
        timeframe="1h",
        direction=TrendDirection.UP,
        strength=0.8,
        start_time=dt,
        end_time=dt,
    )
    market_cont = market_state.model_copy(update={"trend": trend})

    quality = create_pattern_quality(80.0)
    pattern = PatternCandidate(
        candidate_id="pat-cont-1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.BULL_FLAG,
        direction=PatternDirection.BULLISH,
        status=PatternStatus.DEVELOPING,
        points=[],
        trendlines=[],
        score=0.85,
        quality=quality,
        detected_at=dt,
    )
    pattern_cont = pattern_state.model_copy(update={"candidate_patterns": [pattern]})

    signal = strat.evaluate(market_cont, pattern_cont, confluence_state)
    assert signal is not None
    assert signal.decision == StrategyDecision.BUY
    assert signal.strategy_type == StrategyType.CONTINUATION
    assert signal.confidence == 0.77  # Normalized (75.0 * 0.6) + (80.0 * 0.4) = 77.0 -> 0.77


def test_range_strategy(base_context):
    """Test RangeStrategy evaluate logic."""
    market_state, pattern_state, confluence_state = base_context
    strat = RangeStrategy(confluence_min=65.0)

    assert strat.evaluate(market_state, pattern_state, confluence_state) is None

    dt = datetime.now(timezone.utc)
    trend = TrendState(
        symbol="BTCUSDT",
        timeframe="1h",
        direction=TrendDirection.SIDEWAYS,
        strength=0.3,
        start_time=dt,
        end_time=dt,
    )
    volume = VolumeState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume_ma=100.0,
        relative_volume=0.8,
        normalized_volume=0.8,
        expansion_state=VolumeExpansionState.NORMAL,
        volume_trend="DOWN",
        buying_pressure=0.5,
        selling_pressure=0.5,
        updated_at=dt,
    )
    swing = SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        index=10,
        price=10.0,  # near support
        point_type=SwingType.LOW,
        timestamp=dt,
    )
    sr_support = SRLevel(
        symbol="BTCUSDT",
        timeframe="1h",
        price=9.5,
        level_type="SUPPORT",
        strength=0.9,
        touch_count=3,
    )
    sr_resistance = SRLevel(
        symbol="BTCUSDT",
        timeframe="1h",
        price=20.0,
        level_type="RESISTANCE",
        strength=0.9,
        touch_count=3,
    )
    market_range = market_state.model_copy(update={
        "trend": trend,
        "volume": volume,
        "swings": [swing],
        "sr_levels": [sr_support, sr_resistance],
    })

    pattern = PatternCandidate(
        candidate_id="pat-range-1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.RECTANGLE,
        direction=PatternDirection.BULLISH,
        status=PatternStatus.DEVELOPING,
        points=[],
        trendlines=[],
        score=0.8,
        quality=None,
        detected_at=dt,
    )
    pattern_range = pattern_state.model_copy(update={"candidate_patterns": [pattern]})

    # Near support -> BUY setup
    signal = strat.evaluate(market_range, pattern_range, confluence_state)
    assert signal is not None
    assert signal.decision == StrategyDecision.BUY
    assert signal.strategy_type == StrategyType.RANGE
    assert signal.confidence == 0.75


def test_mean_reversion_strategy(base_context):
    """Test MeanReversionStrategy evaluate logic."""
    market_state, pattern_state, confluence_state = base_context
    strat = MeanReversionStrategy(confluence_min=70.0)

    assert strat.evaluate(market_state, pattern_state, confluence_state) is None

    dt = datetime.now(timezone.utc)
    align = TimeframeAlignment(
        dominant_trend=TrendDirection.SIDEWAYS,
        alignment_score=0.5,
        conflict_score=0.5,
        higher_timeframe_confirmation=False,
    )
    context = MarketContext(
        symbol="BTCUSDT",
        timeframe="1h",
        dominant_trend=TrendDirection.SIDEWAYS,
        regime=MarketRegime.VOLATILE,
        alignment=align,
        timestamp=dt,
    )
    swing = SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        index=10,
        price=19.8,  # near supply zone
        point_type=SwingType.HIGH,
        timestamp=dt,
    )
    zone = Zone(
        symbol="BTCUSDT",
        timeframe="1h",
        zone_id="zone-supply",
        zone_type=ZoneType.SUPPLY,
        lower_bound=19.0,
        upper_bound=20.0,
        volume_at_creation=1000.0,
        is_invalidated=False,
    )
    market_mr = market_state.model_copy(update={
        "market_context": context,
        "swings": [swing],
        "zones": [zone],
    })

    # Near supply -> SELL setup
    signal = strat.evaluate(market_mr, pattern_state, confluence_state)
    assert signal is not None
    assert signal.decision == StrategyDecision.SELL
    assert signal.strategy_type == StrategyType.MEAN_REVERSION
    assert signal.confidence == 0.75


def test_momentum_strategy(base_context):
    """Test MomentumStrategy evaluate logic."""
    market_state, pattern_state, confluence_state = base_context
    strat = MomentumStrategy(confluence_min=70.0, rvol_min=1.5, strength_min=0.7)

    assert strat.evaluate(market_state, pattern_state, confluence_state) is None

    dt = datetime.now(timezone.utc)
    trend = TrendState(
        symbol="BTCUSDT",
        timeframe="1h",
        direction=TrendDirection.UP,
        strength=0.85,
        start_time=dt,
        end_time=dt,
    )
    volume = VolumeState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume_ma=100.0,
        relative_volume=1.9,
        normalized_volume=1.9,
        expansion_state=VolumeExpansionState.EXPANSION,
        volume_trend="UP",
        buying_pressure=0.7,
        selling_pressure=0.3,
        updated_at=dt,
    )
    market_mom = market_state.model_copy(update={"trend": trend, "volume": volume})

    signal = strat.evaluate(market_mom, pattern_state, confluence_state)
    assert signal is not None
    assert signal.decision == StrategyDecision.BUY
    assert signal.strategy_type == StrategyType.MOMENTUM
    assert signal.confidence == 0.7667


def test_strategy_selector_and_engine(base_context):
    """Verify StrategySelector ranking and StrategyEngine context validation."""
    market_state, pattern_state, confluence_state = base_context
    
    # When no strategy fires, should return WAIT fallback
    selector = StrategySelector()
    best_sig = selector.select_best_signal(market_state, pattern_state, confluence_state)
    assert best_sig.decision == StrategyDecision.WAIT
    assert best_sig.confidence == 0.0

    # Test Selector ranking multiple active strategies
    dt = datetime.now(timezone.utc)
    # Trend Strategy configuration to trigger
    trend = TrendState(
        symbol="BTCUSDT",
        timeframe="1h",
        direction=TrendDirection.UP,
        strength=0.9,
        start_time=dt,
        end_time=dt,
    )
    bos = BOSRecord(
        symbol="BTCUSDT",
        timeframe="1h",
        level_breached=100.0,
        direction="UP",
        break_timestamp=dt,
        volume_at_break=1000.0,
    )
    
    # Momentum Strategy configuration to trigger
    volume = VolumeState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume_ma=100.0,
        relative_volume=2.0,
        normalized_volume=2.0,
        expansion_state=VolumeExpansionState.EXPANSION,
        volume_trend="UP",
        buying_pressure=0.8,
        selling_pressure=0.2,
        updated_at=dt,
    )
    
    market_both = market_state.model_copy(update={
        "trend": trend,
        "bos_history": [bos],
        "volume": volume,
    })

    # Run Selector: Momentum vs Trend
    best_sig = selector.select_best_signal(market_both, pattern_state, confluence_state)
    assert best_sig.strategy_type == StrategyType.TREND_FOLLOWING
    assert best_sig.decision == StrategyDecision.BUY
    assert best_sig.confidence == 0.83

    # Verify StrategyEngine wrapper
    engine = StrategyEngine(selector=selector)
    engine_sig = engine.evaluate(market_both, pattern_state, confluence_state)
    assert engine_sig.strategy_type == StrategyType.TREND_FOLLOWING
    assert engine_sig.decision == StrategyDecision.BUY
    assert engine_sig.confidence == 0.83

    # Fail validation
    bad_confluence = confluence_state.model_copy(update={
        "score": confluence_state.score.model_copy(update={"overall_score": 10.0})
    })
    engine_sig = engine.evaluate(market_both, pattern_state, bad_confluence)
    assert engine_sig.decision == StrategyDecision.WAIT
    assert engine_sig.confidence == 0.0
