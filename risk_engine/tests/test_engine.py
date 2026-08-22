"""Unit tests for the Risk Engine decision and scoring core."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from trading_context.core.models import TradingContext
from market_intelligence.core.models import MarketState, SessionState
from market_intelligence.core.enums import SessionName
from strategy.core.models import StrategyState
from confluence.core.models import ConfluenceState, ConfluenceScore
from confluence.core.enums import SetupGrade
from risk_engine.core.enums import RiskDecision, RiskSeverity
from risk_engine.core.models import RiskFactor
from risk_engine.analysis.risk_engine import RiskEngine


@pytest.fixture
def dummy_context() -> TradingContext:
    dt = datetime.now(timezone.utc)
    session_state = SessionState(
        symbol="BTCUSDT",
        session_name=SessionName.NEW_YORK,
        session_high=50000.0,
        session_low=49000.0,
    )
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=dt,
        session=session_state,
    )
    strategy_state = StrategyState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    return TradingContext(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=market_state,
        strategy_state=strategy_state,
        generated_at=dt,
    )


def test_risk_engine_decision_allow(dummy_context):
    """Verify that low risk results in an ALLOW decision."""
    engine = RiskEngine()
    
    # Midweek, low drawdown, low losses, no news, correct session
    # Friday morning (weekday 4, hour 10 is not weekend close yet)
    dt = datetime(2026, 6, 26, 10, 0, 0, tzinfo=timezone.utc)
    ctx = dummy_context.model_copy(update={"generated_at": dt})

    assessment = engine.evaluate(
        ctx,
        current_daily_loss_pct=0.0,
        current_daily_trades=0,
        daily_stop_reached=False,
        current_drawdown_pct=0.0,
        weekend_block_active=True,
        market_closed=False,
        low_liquidity_period=False,
        bid_ask_spread=0.001,
        current_volume=100.0,
        high_impact_news_active=False,
    )

    assert assessment.overall_score == 100.0
    assert assessment.decision == RiskDecision.ALLOW
    assert not assessment.factors
    assert not assessment.violations


def test_risk_engine_decision_block_critical_violation(dummy_context):
    """Verify that a CRITICAL severity violation results in a BLOCK decision even with a high score."""
    engine = RiskEngine()

    # Weekend (Friday 22:00 UTC) triggers weekend block validator (CRITICAL violation)
    dt_weekend = datetime(2026, 6, 26, 22, 0, 0, tzinfo=timezone.utc)
    ctx = dummy_context.model_copy(update={"generated_at": dt_weekend})

    assessment = engine.evaluate(
        ctx,
        weekend_block_active=True,
        current_daily_loss_pct=0.0,
        current_daily_trades=0,
        daily_stop_reached=False,
        current_drawdown_pct=0.0,
        market_closed=False,
        low_liquidity_period=False,
        bid_ask_spread=0.001,
        current_volume=100.0,
        high_impact_news_active=False,
    )

    assert assessment.decision == RiskDecision.BLOCK
    assert any(f.severity == RiskSeverity.CRITICAL for f in assessment.factors)


def test_risk_engine_decision_block_low_score(dummy_context):
    """Verify that a score below 80.0 results in a BLOCK decision."""
    engine = RiskEngine()

    dt = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
    ctx = dummy_context.model_copy(update={"generated_at": dt})

    # Cause multiple non-critical violations that accumulate to > 20.0 penalty
    # 1. current_daily_trades (11) -> 25.0 penalty
    # 2. current_drawdown_pct (0.04) -> 10.0 penalty
    # Total penalty = 35.0 -> Score = 65.0
    assessment = engine.evaluate(
        ctx,
        current_daily_trades=11,
        max_daily_trades=10,
        current_drawdown_pct=0.041,
        max_drawdown_pct=0.05,
        weekend_block_active=True,
        market_closed=False,
        low_liquidity_period=False,
        bid_ask_spread=0.001,
        current_volume=100.0,
        high_impact_news_active=False,
    )

    assert assessment.overall_score == 65.0
    assert assessment.decision == RiskDecision.BLOCK


def test_risk_engine_decision_review(dummy_context):
    """Verify that a score between 80.0 and 85.0 or a HIGH severity violation (no CRITICAL) results in a REVIEW."""
    engine = RiskEngine()

    dt = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
    
    # We want a Weak confluence (overall_score = 45.0) which adds a 20.0 penalty -> Score = 80.0
    score = ConfluenceScore(
        overall_score=45.0, setup_grade=SetupGrade.C, trend_score=40, structure_score=40,
        liquidity_score=40, zone_score=40, volume_score=40, regime_score=40, session_score=40,
        mtf_score=40, correlation_score=40, pattern_score=40, quality_score=40,
        conflict_penalty=0.0,
    )
    conf_state = ConfluenceState(
        symbol="BTCUSDT",
        timeframe="1h",
        score=score,
        updated_at=dt,
    )
    
    ctx = dummy_context.model_copy(
        update={
            "generated_at": dt,
            "confluence_state": conf_state,
        }
    )

    assessment = engine.evaluate(
        ctx,
        current_daily_loss_pct=0.0,
        current_daily_trades=0,
        daily_stop_reached=False,
        current_drawdown_pct=0.0,
        weekend_block_active=True,
        market_closed=False,
        low_liquidity_period=False,
        bid_ask_spread=0.001,
        current_volume=100.0,
        high_impact_news_active=False,
    )

    assert assessment.overall_score == 80.0
    assert assessment.decision == RiskDecision.REVIEW


def test_risk_engine_validator_failsafe(dummy_context):
    """Verify that a validator raising an exception is handled gracefully via failsafe fallback."""
    engine = RiskEngine()

    # Mock a validator that raises an exception
    bad_validator = MagicMock()
    bad_validator.validate.side_effect = Exception("Failing validator")
    engine._validators = [bad_validator]

    assessment = engine.evaluate(dummy_context)

    # Failsafe should log, add factor with score 25.0 (penalty) and HIGH severity
    assert assessment.overall_score == 75.0  # 100 - 25
    assert assessment.decision == RiskDecision.BLOCK  # score 75.0 < 80.0 -> BLOCK
    assert len(assessment.factors) == 1
    assert assessment.factors[0].severity == RiskSeverity.HIGH
    assert "Failing validator" in assessment.violations[0]
