"""Unit tests for Confluence Engine scoring components."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import (
    TrendDirection,
    ZoneType,
    SessionName,
    MarketRegime,
)
from market_intelligence.core.models import (
    MarketState,
    TrendState,
    LiquidityState,
    Zone,
    SessionState,
    VolumeState,
    ContextState,
    MarketContext,
    TimeframeAlignment,
    SwingPoint,
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
    SupportingFactor,
    ConflictingFactor,
)
from confluence.analysis.trend_score import evaluate_trend
from confluence.analysis.structure_score import evaluate_structure
from confluence.analysis.liquidity_score import evaluate_liquidity
from confluence.analysis.zone_score import evaluate_zones
from confluence.analysis.volume_score import evaluate_volume
from confluence.analysis.regime_score import evaluate_regime
from confluence.analysis.session_score import evaluate_session
from confluence.analysis.mtf_score import evaluate_mtf
from confluence.analysis.correlation_score import evaluate_correlation
from confluence.analysis.pattern_score import evaluate_pattern
from confluence.analysis.quality_score import evaluate_quality
from confluence.analysis.conflict_engine import ConflictEngine
from confluence.analysis.confluence_engine import ConfluenceEngine


@pytest.fixture
def base_market_state() -> MarketState:
    """Fixture for a baseline MarketState."""
    dt = datetime.now(timezone.utc)
    return MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=dt,
    )


def test_trend_score(base_market_state):
    """Test evaluate_trend with different alignments."""
    # Sideways/neutral trend case
    score, supporting, conflicting = evaluate_trend(base_market_state)
    assert score == 50.0
    assert not supporting
    assert not conflicting

    # Bullish trend case
    dt = datetime.now(timezone.utc)
    trend_state = TrendState(
        symbol="BTCUSDT",
        timeframe="1h",
        direction=TrendDirection.UP,
        strength=0.8,
        start_time=dt,
        end_time=dt,
    )
    market_state = base_market_state.model_copy(update={"trend": trend_state})

    score, supporting, conflicting = evaluate_trend(
        market_state, PatternDirection.BULLISH
    )
    assert score == 100.0
    assert len(supporting) == 1
    assert supporting[0].category == "TREND"
    assert not conflicting

    # Counter-trend case
    score, supporting, conflicting = evaluate_trend(
        market_state, PatternDirection.BEARISH
    )
    assert score == 30.0
    assert not supporting
    assert len(conflicting) == 1
    assert conflicting[0].penalty == 3.0


def test_structure_score(base_market_state):
    """Test evaluate_structure."""
    score, supporting, conflicting = evaluate_structure(base_market_state)
    assert score == 70.0

    # Mock structure shift or continuation history
    # BOS only
    from market_intelligence.core.models import BOSRecord
    dt = datetime.now(timezone.utc)
    bos = BOSRecord(
        symbol="BTCUSDT",
        timeframe="1h",
        level_breached=50000.0,
        direction="UP",
        break_timestamp=dt,
        volume_at_break=100.0,
    )
    market_state = base_market_state.model_copy(update={"bos_history": [bos]})
    score, supporting, conflicting = evaluate_structure(market_state)
    assert score == 85.0
    assert len(supporting) == 1

    # CHoCH
    from market_intelligence.core.models import CHoCHRecord
    choch = CHoCHRecord(
        symbol="BTCUSDT",
        timeframe="1h",
        level_breached=49000.0,
        direction="BULLISH_TO_BEARISH",
        trigger_timestamp=dt,
    )
    market_state = base_market_state.model_copy(update={"choch_history": [choch]})
    score, supporting, conflicting = evaluate_structure(market_state)
    assert score == 90.0
    assert len(supporting) == 1


def test_liquidity_score(base_market_state):
    """Test evaluate_liquidity."""
    score, supporting, conflicting = evaluate_liquidity(base_market_state)
    assert score == 70.0

    # Low swept liquidity
    liq_state = LiquidityState(
        symbol="BTCUSDT",
        timeframe="1h",
        buy_side_pools=[],
        sell_side_pools=[],
        swept_levels=[49000.0],
    )
    # Using dynamic attributes that map to swept low/high
    # Let's mock swept_low=True
    class MockLiquidity:
        swept_low = True
        swept_high = False
        buy_side_pools = []
        sell_side_pools = []
        swept_levels = []

    market_state = base_market_state.model_copy(update={"liquidity": MockLiquidity()})
    score, supporting, conflicting = evaluate_liquidity(
        market_state, PatternDirection.BULLISH
    )
    assert score == 95.0
    assert len(supporting) == 1


def test_zone_score(base_market_state):
    """Test evaluate_zones."""
    score, supporting, conflicting = evaluate_zones(base_market_state)
    assert score == 70.0

    # Zone mitigation check
    dt = datetime.now(timezone.utc)
    swing = SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type="LOW",
        price=50005.0,
        timestamp=dt,
        index=10,
    )
    zone = Zone(
        symbol="BTCUSDT",
        timeframe="1h",
        zone_type=ZoneType.DEMAND,
        upper_bound=50010.0,
        lower_bound=50000.0,
        volume_at_creation=100.0,
    )
    market_state = base_market_state.model_copy(
        update={"swings": [swing], "zones": [zone]}
    )
    score, supporting, conflicting = evaluate_zones(
        market_state, PatternDirection.BULLISH
    )
    assert score == 95.0
    assert len(supporting) == 1


def test_volume_score(base_market_state):
    """Test evaluate_volume."""
    score, supporting, conflicting = evaluate_volume(base_market_state)
    assert score == 75.0

    # High volume
    class MockVolumeHigh:
        relative_volume = 1.8
        average_volume = 100.0
    market_state = base_market_state.model_copy(update={"volume": MockVolumeHigh()})
    score, supporting, conflicting = evaluate_volume(market_state)
    assert score == 90.0
    assert len(supporting) == 1

    # Low volume
    class MockVolumeLow:
        relative_volume = 0.3
        average_volume = 100.0
    market_state = base_market_state.model_copy(update={"volume": MockVolumeLow()})
    score, supporting, conflicting = evaluate_volume(market_state)
    assert score == 50.0
    assert len(conflicting) == 1
    assert conflicting[0].penalty == 2.0


def test_regime_score(base_market_state):
    """Test evaluate_regime."""
    score, supporting, conflicting = evaluate_regime(base_market_state)
    assert score == 75.0

    market_state = base_market_state.model_copy(update={"market_phase_state": "TrendingUp"})
    score, supporting, conflicting = evaluate_regime(market_state)
    assert score == 85.0
    assert len(supporting) == 1


def test_session_score(base_market_state):
    """Test evaluate_session."""
    score, supporting, conflicting = evaluate_session(base_market_state)
    assert score == 75.0

    class MockSession:
        active_sessions = ["London", "Asia"]
    market_state = base_market_state.model_copy(update={"session": MockSession()})
    score, supporting, conflicting = evaluate_session(market_state)
    assert score == 90.0
    assert len(supporting) == 1


def test_mtf_score(base_market_state):
    """Test evaluate_mtf."""
    score, supporting, conflicting = evaluate_mtf(base_market_state)
    assert score == 75.0

    dt = datetime.now(timezone.utc)
    alignment = TimeframeAlignment(
        dominant_trend=TrendDirection.UP,
        alignment_score=0.9,
        conflict_score=0.1,
        higher_timeframe_confirmation=True,
        timeframe_trends={},
    )
    context = MarketContext(
        symbol="BTCUSDT",
        timeframe="1h",
        dominant_trend=TrendDirection.UP,
        regime=MarketRegime.TRENDING,
        alignment=alignment,
        timestamp=dt,
    )
    market_state = base_market_state.model_copy(update={"market_context": context})
    # HTF trend match
    score, supporting, conflicting = evaluate_mtf(
        market_state, PatternDirection.BULLISH
    )
    assert score == 95.0
    assert len(supporting) == 1

    # HTF trend conflict
    score, supporting, conflicting = evaluate_mtf(
        market_state, PatternDirection.BEARISH
    )
    assert score == 40.0
    assert len(conflicting) == 1
    assert conflicting[0].penalty == 2.0


def test_correlation_score(base_market_state):
    """Test evaluate_correlation."""
    score, supporting, conflicting = evaluate_correlation(base_market_state)
    assert score == 100.0

    dt = datetime.now(timezone.utc)
    alignment = TimeframeAlignment(
        dominant_trend=TrendDirection.UP,
        alignment_score=0.9,
        conflict_score=0.1,
        higher_timeframe_confirmation=True,
        timeframe_trends={},
    )
    context = MarketContext(
        symbol="BTCUSDT",
        timeframe="1h",
        dominant_trend=TrendDirection.UP,
        regime=MarketRegime.TRENDING,
        alignment=alignment,
        correlation={"ETHUSDT": 0.85, "SOLUSDT": 0.90},
        timestamp=dt,
    )
    market_state = base_market_state.model_copy(update={"market_context": context})

    # High correlation
    score, supporting, conflicting = evaluate_correlation(market_state)
    assert score == 60.0
    assert len(conflicting) == 1
    assert conflicting[0].penalty == 1.5

    # Low correlation
    context_low = context.model_copy(update={"correlation": {"ETHUSDT": 0.1, "SOLUSDT": 0.2}})
    market_state_low = base_market_state.model_copy(update={"market_context": context_low})
    score, supporting, conflicting = evaluate_correlation(market_state_low)
    assert score == 95.0
    assert len(supporting) == 1


def test_pattern_score(base_market_state):
    """Test evaluate_pattern."""
    # Pattern state is None
    score, supporting, conflicting = evaluate_pattern(base_market_state, None)
    assert score == 50.0

    # No patterns
    pattern_state = PatternState(symbol="BTCUSDT", timeframe="1h")
    score, supporting, conflicting = evaluate_pattern(base_market_state, pattern_state)
    assert score == 50.0

    dt = datetime.now(timezone.utc)
    point = PatternPoint(price=10.0, timestamp=dt, index=0, point_label="A")
    match = PatternMatch(
        match_id="id1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_TOP,
        direction=PatternDirection.BEARISH,
        status=PatternStatus.CONFIRMED,
        points=[point],
        trendlines=[],
        fit_score=0.9,
        confirmed_at=dt,
    )
    pattern_state = PatternState(
        symbol="BTCUSDT", timeframe="1h", active_patterns=[match]
    )

    # Active matching pattern
    score, supporting, conflicting = evaluate_pattern(
        base_market_state, pattern_state, PatternDirection.BEARISH
    )
    assert score == 95.0
    assert len(supporting) == 1

    # Active opposing pattern
    score, supporting, conflicting = evaluate_pattern(
        base_market_state, pattern_state, PatternDirection.BULLISH
    )
    assert score == 40.0
    assert len(conflicting) == 1
    assert conflicting[0].penalty == 3.0


def test_quality_score(base_market_state):
    """Test evaluate_quality."""
    score, supporting, conflicting = evaluate_quality(base_market_state, None)
    assert score == 50.0

    dt = datetime.now(timezone.utc)
    point = PatternPoint(price=10.0, timestamp=dt, index=0, point_label="A")
    quality = PatternQuality(
        overall_score=85.0,
        geometry_score=80.0,
        symmetry_score=80.0,
        breakout_score=80.0,
        regression_score=80.0,
        touch_score=80.0,
        volume_score=80.0,
        volatility_score=80.0,
        age_score=80.0,
        completion_score=80.0,
        confidence=80.0,
        evaluated_at=dt,
        explanation="Excellent structure",
    )
    match = PatternMatch(
        match_id="id1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_TOP,
        direction=PatternDirection.BEARISH,
        status=PatternStatus.CONFIRMED,
        points=[point],
        trendlines=[],
        fit_score=0.9,
        confirmed_at=dt,
        quality=quality,
    )
    pattern_state = PatternState(
        symbol="BTCUSDT", timeframe="1h", active_patterns=[match]
    )

    score, supporting, conflicting = evaluate_quality(
        base_market_state, pattern_state, PatternDirection.BEARISH
    )
    assert score == 85.0
    assert len(supporting) == 1


def test_conflict_engine():
    """Test ConflictEngine penalty calculations."""
    engine = ConflictEngine(max_penalty=6.0)

    # Empty
    assert engine.calculate_penalty([]) == 0.0

    # Under cap
    factors = [
        ConflictingFactor(name="F1", category="CAT", penalty=2.0, description="D"),
        ConflictingFactor(name="F2", category="CAT", penalty=3.0, description="D"),
    ]
    assert engine.calculate_penalty(factors) == 5.0

    # Over cap
    factors_over = factors + [
        ConflictingFactor(name="F3", category="CAT", penalty=2.5, description="D"),
    ]
    assert engine.calculate_penalty(factors_over) == 6.0


def test_confluence_engine(base_market_state):
    """Test ConfluenceEngine overall scoring."""
    engine = ConfluenceEngine()

    # Base execution
    score = engine.evaluate(base_market_state, None)
    assert isinstance(score.overall_score, float)
    assert score.setup_grade == SetupGrade.C  # Baseline score is moderate
