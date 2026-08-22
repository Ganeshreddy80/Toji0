"""Unit tests for the Position Sizing algorithms/calculators."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from trading_context.core.models import TradingContext
from market_intelligence.core.models import MarketState, VolumeState
from market_intelligence.core.enums import VolumeExpansionState
from risk_engine.core.models import RiskAssessment
from risk_engine.core.enums import RiskDecision
from strategy.core.models import StrategyState
from position_sizing.analysis.fixed_fractional import FixedFractionalCalculator
from position_sizing.analysis.fixed_risk import FixedRiskCalculator
from position_sizing.analysis.atr_position import ATRPositionCalculator
from position_sizing.analysis.volatility_position import VolatilityPositionCalculator
from position_sizing.analysis.kelly_position import KellyPositionCalculator


@pytest.fixture
def dummy_context() -> TradingContext:
    dt = datetime.now(timezone.utc)
    # Give volume state an ATR for calculators that depend on ATR
    volume_state = VolumeState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume_ma=100.0,
        normalized_volume=1.0,
        expansion_state=VolumeExpansionState.NORMAL,
        atr=2.5,
    )
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume=volume_state,
        updated_at=dt,
    )
    strategy_state = StrategyState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    return TradingContext(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=market_state,
        strategy_state=strategy_state,
        generated_at=dt,
    )


@pytest.fixture
def dummy_risk() -> RiskAssessment:
    return RiskAssessment(
        overall_score=100.0,
        decision=RiskDecision.ALLOW,
    )


def test_fixed_fractional_calculator(dummy_context, dummy_risk):
    """Verify Fixed Fractional calculator handles standard risk percentage rules."""
    calc = FixedFractionalCalculator()

    # Case 1: Standard calculation (1% risk on 100,000 balance = $1,000 risk, stop distance = 5.0)
    # quantity = 1000 / 5 = 200.0
    qty, reasons = calc.calculate(
        dummy_context,
        dummy_risk,
        account_balance=100000.0,
        risk_percent=0.01,
        stop_distance=5.0,
    )
    assert qty == 200.0
    assert any("Fixed Fractional" in r for r in reasons)

    # Case 2: Zero stop distance (with valid balance) is rejected
    qty2, reasons2 = calc.calculate(
        dummy_context,
        dummy_risk,
        account_balance=100000.0,
        stop_distance=0.0,
    )
    assert qty2 == 0.0
    assert any("Stop distance must be positive" in r for r in reasons2)


def test_fixed_risk_calculator(dummy_context, dummy_risk):
    """Verify Fixed Risk calculator risks exactly the specified dollar amount."""
    calc = FixedRiskCalculator()

    # Risk fixed $150 with stop distance = 3.0
    # quantity = 150 / 3 = 50.0
    qty, reasons = calc.calculate(
        dummy_context,
        dummy_risk,
        risk_amount=150.0,
        stop_distance=3.0,
    )
    assert qty == 50.0
    assert any("Fixed Risk" in r for r in reasons)


def test_atr_position_calculator(dummy_context, dummy_risk):
    """Verify ATR-based stop distance sizing."""
    calc = ATRPositionCalculator()

    # Dummy context has atr=2.5.
    # stop_distance = atr * multiplier = 2.5 * 2.0 = 5.0
    # Balance = 100,000, risk_pct = 1% => risk = 1,000
    # quantity = 1000 / 5 = 200.0
    qty, reasons = calc.calculate(
        dummy_context,
        dummy_risk,
        account_balance=100000.0,
        risk_percent=0.01,
        atr_multiplier=2.0,
    )
    assert qty == 200.0
    assert any("ATR Sizing" in r for r in reasons)


def test_volatility_position_calculator(dummy_context, dummy_risk):
    """Verify Volatility sizing scales down position size under high volatility."""
    calc = VolatilityPositionCalculator()

    # Standard fractional size: balance=100,000, risk_pct=1% => $1000 risk. stop_dist=5.0 => qty=200.0
    # Current ATR = 2.5 (from dummy_context). Historical Avg ATR = 1.25.
    # Scale factor = Avg / Current = 1.25 / 2.5 = 0.5.
    # Adjusted quantity = 200.0 * 0.5 = 100.0
    qty, reasons = calc.calculate(
        dummy_context,
        dummy_risk,
        account_balance=100000.0,
        risk_percent=0.01,
        stop_distance=5.0,
        historical_avg_atr=1.25,
    )
    assert qty == 100.0
    assert any("Volatility Adjuster" in r for r in reasons)


def test_kelly_position_calculator(dummy_context, dummy_risk):
    """Verify Kelly Criterion calculates win-rate payoff-ratio scaling correctly."""
    calc = KellyPositionCalculator()

    # Win rate = 60%, Payoff = 2.0
    # Kelly = 0.6 - (1 - 0.6) / 2.0 = 0.6 - 0.2 = 0.4 (40%)
    # Half Kelly multiplier = 0.5 => effective risk pct = 20%
    # Risk amount = 100,000 * 20% = 20,000
    # Stop distance = 10.0 => qty = 20,000 / 10 = 2000.0
    qty, reasons = calc.calculate(
        dummy_context,
        dummy_risk,
        win_rate=0.60,
        payoff_ratio=2.0,
        kelly_fraction="HALF",
        account_balance=100000.0,
        stop_distance=10.0,
    )
    assert qty == 2000.0
    assert any("Kelly (HALF)" in r for r in reasons)


# ---------------------------------------------------------------------------
# Task 2A — Calculator-level fail-closed: missing balance
# ---------------------------------------------------------------------------

def test_fixed_fractional_missing_balance(dummy_context, dummy_risk):
    """Task 2A: FixedFractional must reject when account balance is absent."""
    calc = FixedFractionalCalculator()
    qty, reasons = calc.calculate(dummy_context, dummy_risk, stop_distance=5.0)
    assert qty == 0.0
    assert any("balance" in r.lower() for r in reasons)


def test_atr_position_missing_balance(dummy_context, dummy_risk):
    """Task 2A: ATRPosition must reject when account balance is absent."""
    calc = ATRPositionCalculator()
    qty, reasons = calc.calculate(dummy_context, dummy_risk, atr_multiplier=2.0)
    assert qty == 0.0
    assert any("balance" in r.lower() for r in reasons)


def test_kelly_missing_balance(dummy_context, dummy_risk):
    """Task 2A: KellyPosition must reject when account balance is absent."""
    from position_sizing.analysis.kelly_position import KellyPositionCalculator
    calc = KellyPositionCalculator()
    qty, reasons = calc.calculate(
        dummy_context, dummy_risk,
        win_rate=0.60, payoff_ratio=2.0, stop_distance=10.0,
    )
    assert qty == 0.0
    assert any("balance" in r.lower() for r in reasons)


def test_fractional_kelly_missing_balance(dummy_context, dummy_risk):
    """Task 2A: FractionalKelly must reject when account balance is absent."""
    from position_sizing.analysis.fractional_kelly import FractionalKellyCalculator
    calc = FractionalKellyCalculator()
    qty, reasons = calc.calculate(
        dummy_context, dummy_risk,
        win_rate=0.55, rr_ratio=2.0, stop_distance=5.0,
    )
    assert qty == 0.0
    assert any("balance" in r.lower() for r in reasons)


def test_portfolio_balanced_missing_balance(dummy_context, dummy_risk):
    """Task 2A: PortfolioBalanced must reject when account balance is absent."""
    from position_sizing.analysis.portfolio_balanced import PortfolioBalancedCalculator
    calc = PortfolioBalancedCalculator()
    qty, reasons = calc.calculate(
        dummy_context, dummy_risk,
        max_open_positions=5, entry_price=100.0,
    )
    assert qty == 0.0
    assert any("balance" in r.lower() for r in reasons)
