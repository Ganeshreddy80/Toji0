"""Unit tests for the Strategy Eligibility Evaluator."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from intelligence.models import MarketPulse
from intelligence.eligibility.evaluator import StrategyEligibilityConstraints, StrategyEligibilityEvaluator


@pytest.fixture
def evaluator() -> StrategyEligibilityEvaluator:
    """Provide a StrategyEligibilityEvaluator instance."""
    return StrategyEligibilityEvaluator()


@pytest.fixture
def constraints() -> StrategyEligibilityConstraints:
    """Provide typical StrategyEligibilityConstraints."""
    return StrategyEligibilityConstraints(
        strategy_id="strat-1",
        target_regimes=["Markup", "Expansion"],
        min_market_health=0.4,
        max_market_risk=0.6,
        max_volatility=5.0,
    )


@pytest.fixture
def healthy_pulse() -> MarketPulse:
    """Provide a healthy MarketPulse snapshot."""
    return MarketPulse(
        trend=0.5,
        momentum=0.4,
        liquidity=1.5,
        risk=0.2,
        volatility=1.2,
        participation=1.1,
        fear=40.0,
        confidence=0.8,
        overall_score=0.7,
        timestamp=datetime.now(timezone.utc),
    )


def test_eligible_condition(
    evaluator: StrategyEligibilityEvaluator,
    constraints: StrategyEligibilityConstraints,
    healthy_pulse: MarketPulse,
) -> None:
    """Test standard eligible setup."""
    is_eligible, reason = evaluator.evaluate(constraints, healthy_pulse, "Markup")
    assert is_eligible is True
    assert reason == "Eligible"


def test_regime_mismatch(
    evaluator: StrategyEligibilityEvaluator,
    constraints: StrategyEligibilityConstraints,
    healthy_pulse: MarketPulse,
) -> None:
    """Test eligibility fails when the regime phase does not match targets."""
    is_eligible, reason = evaluator.evaluate(constraints, healthy_pulse, "Markdown")
    assert is_eligible is False
    assert "Regime mismatch" in reason


def test_market_health_check(
    evaluator: StrategyEligibilityEvaluator,
    constraints: StrategyEligibilityConstraints,
) -> None:
    """Test eligibility fails when overall market health is below target."""
    poor_pulse = MarketPulse(
        trend=-0.5,
        momentum=-0.4,
        liquidity=0.2,
        risk=0.8,
        volatility=4.5,
        participation=0.5,
        fear=90.0,
        confidence=0.5,
        overall_score=0.2,  # < 0.4 min health requirement
        timestamp=datetime.now(timezone.utc),
    )

    is_eligible, reason = evaluator.evaluate(constraints, poor_pulse, "Markup")
    assert is_eligible is False
    assert "Low market health" in reason


def test_market_risk_check(
    evaluator: StrategyEligibilityEvaluator,
    constraints: StrategyEligibilityConstraints,
    healthy_pulse: MarketPulse,
) -> None:
    """Test eligibility fails when market risk exceeds strategy allowance."""
    # Modify pulse risk to exceed 0.6 max risk budget
    risky_pulse = MarketPulse(
        trend=0.5,
        momentum=0.4,
        liquidity=1.5,
        risk=0.7,  # > 0.6 max risk allowance
        volatility=1.2,
        participation=1.1,
        fear=75.0,
        confidence=0.8,
        overall_score=0.5,
        timestamp=datetime.now(timezone.utc),
    )

    is_eligible, reason = evaluator.evaluate(constraints, risky_pulse, "Markup")
    assert is_eligible is False
    assert "High market risk" in reason


def test_volatility_check(
    evaluator: StrategyEligibilityEvaluator,
    constraints: StrategyEligibilityConstraints,
    healthy_pulse: MarketPulse,
) -> None:
    """Test eligibility fails when volatility exceeds strategy allowance."""
    # Modify pulse volatility to exceed 5.0 max volatility
    extreme_vol_pulse = MarketPulse(
        trend=0.5,
        momentum=0.4,
        liquidity=1.5,
        risk=0.2,
        volatility=8.5,  # > 5.0 max volatility allowance
        participation=1.1,
        fear=40.0,
        confidence=0.8,
        overall_score=0.7,
        timestamp=datetime.now(timezone.utc),
    )

    is_eligible, reason = evaluator.evaluate(constraints, extreme_vol_pulse, "Markup")
    assert is_eligible is False
    assert "High volatility" in reason
