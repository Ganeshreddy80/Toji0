"""Unit tests for the Risk Engine validators."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from trading_context.core.models import TradingContext
from market_intelligence.core.models import MarketState, VolumeState, MarketContext, SessionState
from market_intelligence.core.enums import MarketRegime, VolumeExpansionState, SessionName, TrendDirection
from strategy.core.models import StrategyState, StrategySignal
from strategy.core.enums import StrategyDecision, StrategyType
from price_action.core.enums import PatternDirection
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState, ConfluenceScore
from confluence.core.enums import SetupGrade
from risk_engine.core.enums import RiskSeverity
from risk_engine.analysis.validators import (
    DailyLossValidator,
    DrawdownValidator,
    VolatilityValidator,
    CorrelationValidator,
    SessionValidator,
    LiquidityValidator,
    NewsValidator,
    WeekendValidator,
    ConflictValidator,
)


@pytest.fixture
def dummy_context() -> TradingContext:
    dt = datetime.now(timezone.utc)
    market_state = MarketState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    strategy_state = StrategyState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    return TradingContext(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=market_state,
        strategy_state=strategy_state,
        generated_at=dt,
    )


def test_daily_loss_validator(dummy_context):
    """Verify DailyLossValidator limits and conditions."""
    v = DailyLossValidator()

    # Pass case
    factor, penalty, reason = v.validate(dummy_context, current_daily_loss_pct=0.01, max_daily_trades=5, current_daily_trades=2)
    assert factor is None
    assert penalty == 0.0

    # Stop out reached
    factor, penalty, reason = v.validate(dummy_context, daily_stop_reached=True)
    assert factor is not None
    assert factor.severity == RiskSeverity.CRITICAL
    assert penalty == 100.0
    assert "Daily stop out" in reason

    # Loss limit exceeded
    factor, penalty, reason = v.validate(dummy_context, current_daily_loss_pct=0.03, daily_loss_limit_pct=0.02)
    assert factor is not None
    assert factor.severity == RiskSeverity.CRITICAL
    assert penalty == 100.0

    # Max trades reached
    factor, penalty, reason = v.validate(dummy_context, current_daily_trades=11, max_daily_trades=10)
    assert factor is not None
    assert factor.severity == RiskSeverity.HIGH
    assert penalty == 25.0


def test_drawdown_validator(dummy_context):
    """Verify DrawdownValidator limits and boundaries."""
    v = DrawdownValidator()

    # Pass case
    factor, penalty, reason = v.validate(dummy_context, current_drawdown_pct=0.01)
    assert factor is None

    # Equity protection level
    factor, penalty, reason = v.validate(dummy_context, current_drawdown_pct=0.12, equity_protection_pct=0.10)
    assert factor.severity == RiskSeverity.CRITICAL
    assert penalty == 100.0

    # Max drawdown exceeded
    factor, penalty, reason = v.validate(dummy_context, current_drawdown_pct=0.06, max_drawdown_pct=0.05)
    assert factor.severity == RiskSeverity.HIGH
    assert penalty == 30.0

    # Drawdown warning (80% boundary)
    factor, penalty, reason = v.validate(dummy_context, current_drawdown_pct=0.041, max_drawdown_pct=0.05)
    assert factor.severity == RiskSeverity.MEDIUM
    assert penalty == 10.0


def test_volatility_validator(dummy_context):
    """Verify VolatilityValidator checks regime, ATR spikes, and volume expansion."""
    v = VolatilityValidator()

    # Pass case
    assert v.validate(dummy_context)[0] is None

    # Volatile regime
    dt = datetime.now(timezone.utc)
    market_context = MarketContext(
        symbol="BTCUSDT",
        timeframe="1h",
        dominant_trend=TrendDirection.UP,
        regime=MarketRegime.VOLATILE,
        alignment=dict(dominant_trend=TrendDirection.UP, alignment_score=1.0, conflict_score=0.0, higher_timeframe_confirmation=True),
        timestamp=dt,
    )
    context_volatile = dummy_context.model_copy(
        update={
            "market_state": dummy_context.market_state.model_copy(
                update={"market_context": market_context}
            )
        }
    )
    factor, penalty, reason = v.validate(context_volatile)
    assert factor.severity == RiskSeverity.MEDIUM
    assert penalty == 15.0

    # Climatic volume
    volume_state = VolumeState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume_ma=100.0,
        normalized_volume=3.5,
        expansion_state=VolumeExpansionState.CLIMATIC,
    )
    context_climatic = dummy_context.model_copy(
        update={
            "market_state": dummy_context.market_state.model_copy(
                update={"volume": volume_state}
            )
        }
    )
    factor, penalty, reason = v.validate(context_climatic)
    assert factor.severity == RiskSeverity.HIGH
    assert penalty == 25.0

    # ATR Spike
    volume_state_atr = VolumeState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume_ma=100.0,
        normalized_volume=1.0,
        expansion_state=VolumeExpansionState.NORMAL,
        atr=50.0,
    )
    context_atr = dummy_context.model_copy(
        update={
            "market_state": dummy_context.market_state.model_copy(
                update={"volume": volume_state_atr}
            )
        }
    )
    factor, penalty, reason = v.validate(context_atr, atr_ma=10.0, volatility_threshold_multiplier=3.0)
    assert factor.severity == RiskSeverity.HIGH
    assert penalty == 30.0


def test_correlation_validator(dummy_context):
    """Verify CorrelationValidator blocks duplicate exposure and highly correlated assets."""
    v = CorrelationValidator()

    # Pass case
    factor, penalty, reason = v.validate(dummy_context, existing_portfolio_symbols=["ETHUSDT"])
    assert factor is None

    # Duplicate exposure
    factor, penalty, reason = v.validate(dummy_context, existing_portfolio_symbols=["BTCUSDT", "ETHUSDT"])
    assert factor.severity == RiskSeverity.HIGH
    assert penalty == 25.0

    # High correlation
    factor, penalty, reason = v.validate(
        dummy_context,
        portfolio_correlations={"BTCUSDT": 0.8},
        max_correlation_limit=0.7,
    )
    assert factor.severity == RiskSeverity.HIGH
    assert penalty == 20.0


def test_session_validator(dummy_context):
    """Verify SessionValidator checks market close and low liquidity gaps."""
    v = SessionValidator()

    # Market closed
    factor, penalty, reason = v.validate(dummy_context, market_closed=True)
    assert factor.severity == RiskSeverity.CRITICAL
    assert penalty == 100.0

    # Low liquidity session gap
    factor, penalty, reason = v.validate(dummy_context, low_liquidity_period=True)
    assert factor.severity == RiskSeverity.MEDIUM
    assert penalty == 15.0

    # Missing active session state in Market State
    factor, penalty, reason = v.validate(dummy_context)
    assert factor.severity == RiskSeverity.MEDIUM
    assert penalty == 15.0


def test_liquidity_validator(dummy_context):
    """Verify LiquidityValidator checks spreads and minimum volumes."""
    v = LiquidityValidator()

    # Pass case
    factor, penalty, reason = v.validate(dummy_context, bid_ask_spread=0.001, max_allowable_spread=0.005, current_volume=10.0)
    assert factor is None

    # Excessive spread
    factor, penalty, reason = v.validate(dummy_context, bid_ask_spread=0.008, max_allowable_spread=0.005)
    assert factor.severity == RiskSeverity.HIGH
    assert penalty == 25.0

    # Low absolute volume
    factor, penalty, reason = v.validate(dummy_context, current_volume=0.5, min_required_volume=1.0)
    assert factor.severity == RiskSeverity.MEDIUM
    assert penalty == 15.0


def test_news_validator(dummy_context):
    """Verify NewsValidator handles active events and restriction windows."""
    v = NewsValidator()

    # Pass case
    assert v.validate(dummy_context)[0] is None

    # Active news release
    factor, penalty, reason = v.validate(dummy_context, high_impact_news_active=True)
    assert factor.severity == RiskSeverity.HIGH
    assert penalty == 30.0

    # Within news window proximity
    factor, penalty, reason = v.validate(dummy_context, news_gap_minutes=15, news_restriction_window_mins=30)
    assert factor.severity == RiskSeverity.HIGH
    assert penalty == 25.0


def test_weekend_validator(dummy_context):
    """Verify WeekendValidator blocks weekend hour stamps."""
    v = WeekendValidator()

    # Midweek date - Wednesday afternoon (should pass)
    dt_wed = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
    ctx_wed = dummy_context.model_copy(update={"generated_at": dt_wed})
    assert v.validate(ctx_wed)[0] is None

    # Weekend - Saturday (should block)
    dt_sat = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)
    ctx_sat = dummy_context.model_copy(update={"generated_at": dt_sat})
    factor, penalty, reason = v.validate(ctx_sat)
    assert factor.severity == RiskSeverity.CRITICAL
    assert penalty == 100.0


def test_conflict_validator(dummy_context):
    """Verify ConflictValidator catches high confluence penalties and signal conflicts."""
    v = ConflictValidator()

    # Pass case
    assert v.validate(dummy_context)[0] is None

    # High confluence conflict penalty
    dt = datetime.now(timezone.utc)
    score = ConfluenceScore(
        overall_score=80.0, setup_grade=SetupGrade.A, trend_score=80, structure_score=80,
        liquidity_score=80, zone_score=80, volume_score=80, regime_score=80, session_score=80,
        mtf_score=80, correlation_score=80, pattern_score=80, quality_score=80,
        conflict_penalty=4.5,
    )
    conf_state = ConfluenceState(symbol="BTCUSDT", timeframe="1h", score=score, updated_at=dt)
    ctx_conf_penalty = dummy_context.model_copy(update={"confluence_state": conf_state})

    factor, penalty, reason = v.validate(ctx_conf_penalty)
    assert factor.severity == RiskSeverity.HIGH
    assert penalty == 30.0

    # Multiple strategy signal conflicts
    sig = StrategySignal(
        signal_id="sig-1", symbol="BTCUSDT", timeframe="1h", direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING, decision=StrategyDecision.BUY, confidence=80,
        confluence_score=80, reasoning="test", detected_at=dt,
        conflicting_factors=["conflict_1", "conflict_2", "conflict_3"],
    )
    ctx_sig_conflict = dummy_context.model_copy(update={"strategy_signal": sig})
    factor, penalty, reason = v.validate(ctx_sig_conflict)
    assert factor.severity == RiskSeverity.HIGH
    assert penalty == 25.0
