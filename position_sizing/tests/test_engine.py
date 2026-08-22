"""Unit tests for the Position Sizing Engine execution and validations."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from trading_context.core.models import TradingContext
from market_intelligence.core.models import MarketState, VolumeState
from market_intelligence.core.enums import VolumeExpansionState
from risk_engine.core.models import RiskAssessment
from risk_engine.core.enums import RiskDecision
from strategy.core.models import StrategyState
from position_sizing.core.enums import SizingStatus, PositionSizingMethod
from position_sizing.analysis.position_engine import PositionSizingEngine


@pytest.fixture
def dummy_context() -> TradingContext:
    dt = datetime.now(timezone.utc)
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


def test_position_engine_decision_allow(dummy_context):
    """Verify standard allowable position calculations pass validations."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(overall_score=95.0, decision=RiskDecision.ALLOW)

    result = engine.calculate_size(
        dummy_context,
        risk,
        account_balance=100000.0,
        risk_percent=0.001,
        stop_distance=5.0,
        take_profit_distance=10.0,
        entry_price=100.0,
        max_leverage=10.0,
    )

    assert result.success
    assert result.status == SizingStatus.APPROVED
    assert result.position_size is not None
    assert result.position_size.quantity == 20.0
    assert result.position_size.leverage == 0.02
    assert result.position_size.margin_required == 2000.0
    assert result.position_size.stop_distance == 5.0
    assert result.position_size.take_profit_distance == 10.0


def test_position_engine_decision_block_risk(dummy_context):
    """Verify that a BLOCK risk decision rejects sizing immediately."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(
        overall_score=50.0,
        decision=RiskDecision.BLOCK,
        violations=["Daily loss limit reached"],
    )

    result = engine.calculate_size(
        dummy_context,
        risk,
        account_balance=100000.0,
        risk_percent=0.01,
        stop_distance=5.0,
        take_profit_distance=10.0,
    )

    assert not result.success
    assert result.status == SizingStatus.REJECTED
    assert result.position_size is None
    assert "Risk assessment rejected" in result.reasons[0]
    assert "Daily loss limit reached" in result.violations


def test_position_engine_violate_max_leverage(dummy_context):
    """Verify leverage limits are checked and violate constraints."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(overall_score=95.0, decision=RiskDecision.ALLOW)

    result = engine.calculate_size(
        dummy_context,
        risk,
        account_balance=1000.0,
        risk_percent=0.02,
        stop_distance=0.1,
        take_profit_distance=1.0,
        entry_price=100.0,
        max_leverage=10.0,
    )

    assert not result.success
    assert result.status == SizingStatus.REJECTED
    assert any("Leverage limit exceeded" in v for v in result.violations)


def test_position_engine_violate_single_trade_risk(dummy_context):
    """Verify single trade risk limit checks."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(overall_score=95.0, decision=RiskDecision.ALLOW)

    result = engine.calculate_size(
        dummy_context,
        risk,
        account_balance=100000.0,
        risk_percent=0.05,
        stop_distance=5.0,
        take_profit_distance=10.0,
        entry_price=100.0,
        max_single_trade_risk_pct=0.01,
    )

    assert not result.success
    assert result.status == SizingStatus.REJECTED
    assert any("Single trade risk limit exceeded" in v for v in result.violations)


# Task 2 Comprehensive Tests

def test_task2_valid_strategy_parameters(dummy_context):
    """Verify valid strategy parameters produce approved sizing with exact stop/tp distances."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(overall_score=90.0, decision=RiskDecision.ALLOW)

    result = engine.calculate_size(
        dummy_context,
        risk,
        account_balance=100000.0,
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        risk_percent=0.001,
    )

    assert result.success
    assert result.status == SizingStatus.APPROVED
    assert result.position_size is not None
    assert result.position_size.stop_distance == 5.0
    assert result.position_size.take_profit_distance == 10.0


def test_task2_missing_stop_loss(dummy_context):
    """Verify missing stop-loss fails closed with SizingStatus.REJECTED."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(overall_score=90.0, decision=RiskDecision.ALLOW)

    result = engine.calculate_size(
        dummy_context,
        risk,
        account_balance=100000.0,
        entry_price=100.0,
        take_profit=110.0,
    )

    assert not result.success
    assert result.status == SizingStatus.REJECTED
    assert result.position_size is None
    assert any("stop-loss" in r.lower() for r in result.reasons + result.violations)


def test_task2_missing_take_profit(dummy_context):
    """Verify missing take-profit fails closed with SizingStatus.REJECTED."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(overall_score=90.0, decision=RiskDecision.ALLOW)

    result = engine.calculate_size(
        dummy_context,
        risk,
        account_balance=100000.0,
        entry_price=100.0,
        stop_loss=95.0,
    )

    assert not result.success
    assert result.status == SizingStatus.REJECTED
    assert result.position_size is None
    assert any("take-profit" in r.lower() for r in result.reasons + result.violations)


def test_task2_missing_both_stop_and_tp(dummy_context):
    """Verify missing both stop-loss and take-profit fails closed."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(overall_score=90.0, decision=RiskDecision.ALLOW)

    result = engine.calculate_size(
        dummy_context,
        risk,
        account_balance=100000.0,
        entry_price=100.0,
    )

    assert not result.success
    assert result.status == SizingStatus.REJECTED
    assert result.position_size is None


def test_task2_invalid_negative_values(dummy_context):
    """Verify negative parameters reject sizing."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(overall_score=90.0, decision=RiskDecision.ALLOW)

    # Negative stop distance
    res1 = engine.calculate_size(
        dummy_context, risk, account_balance=100000.0, entry_price=100.0, stop_distance=-5.0, take_profit_distance=10.0
    )
    assert not res1.success and res1.status == SizingStatus.REJECTED

    # Negative stop loss
    res2 = engine.calculate_size(
        dummy_context, risk, account_balance=100000.0, entry_price=100.0, stop_loss=-95.0, take_profit=110.0
    )
    assert not res2.success and res2.status == SizingStatus.REJECTED

    # Negative take profit
    res3 = engine.calculate_size(
        dummy_context, risk, account_balance=100000.0, entry_price=100.0, stop_loss=95.0, take_profit=-110.0
    )
    assert not res3.success and res3.status == SizingStatus.REJECTED

    # Negative entry price
    res4 = engine.calculate_size(
        dummy_context, risk, account_balance=100000.0, entry_price=-100.0, stop_loss=95.0, take_profit=110.0
    )
    assert not res4.success and res4.status == SizingStatus.REJECTED

    # Negative account balance
    res5 = engine.calculate_size(
        dummy_context, risk, account_balance=-100000.0, entry_price=100.0, stop_loss=95.0, take_profit=110.0
    )
    assert not res5.success and res5.status == SizingStatus.REJECTED


def test_task2_zero_values(dummy_context):
    """Verify zero values reject sizing."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(overall_score=90.0, decision=RiskDecision.ALLOW)

    # Zero stop distance
    res1 = engine.calculate_size(
        dummy_context, risk, account_balance=100000.0, entry_price=100.0, stop_distance=0.0, take_profit_distance=10.0
    )
    assert not res1.success and res1.status == SizingStatus.REJECTED

    # Stop loss equal to entry price (zero distance)
    res2 = engine.calculate_size(
        dummy_context, risk, account_balance=100000.0, entry_price=100.0, stop_loss=100.0, take_profit=110.0
    )
    assert not res2.success and res2.status == SizingStatus.REJECTED

    # Take profit equal to entry price (zero distance)
    res3 = engine.calculate_size(
        dummy_context, risk, account_balance=100000.0, entry_price=100.0, stop_loss=95.0, take_profit=100.0
    )
    assert not res3.success and res3.status == SizingStatus.REJECTED

    # Zero entry price
    res4 = engine.calculate_size(
        dummy_context, risk, account_balance=100000.0, entry_price=0.0, stop_loss=95.0, take_profit=110.0
    )
    assert not res4.success and res4.status == SizingStatus.REJECTED

    # Zero account balance
    res5 = engine.calculate_size(
        dummy_context, risk, account_balance=0.0, entry_price=100.0, stop_loss=95.0, take_profit=110.0
    )
    assert not res5.success and res5.status == SizingStatus.REJECTED


def test_task2_regression_no_fallback_percentages(dummy_context):
    """Regression test ensuring zero fallback percentages (2% stop, 4% tp) remain in position engine."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(overall_score=90.0, decision=RiskDecision.ALLOW)

    # Calling calculate_size with only balance and entry price must NOT generate a position with 2% stop / 4% tp.
    result = engine.calculate_size(dummy_context, risk, account_balance=100000.0, entry_price=100.0)

    assert result.status == SizingStatus.REJECTED
    assert result.position_size is None


# Task 2A — engine-level audit fixes

def test_task2a_unknown_sizing_method_rejected(dummy_context):
    """Task 2A: Engine must return REJECTED (not raise) when an unknown sizing method is configured."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(overall_score=90.0, decision=RiskDecision.ALLOW)

    result = engine.calculate_size(
        dummy_context,
        risk,
        account_balance=100000.0,
        entry_price=100.0,
        stop_distance=5.0,
        take_profit_distance=10.0,
        default_sizing_method="NONEXISTENT_METHOD",
    )

    assert not result.success
    assert result.status == SizingStatus.REJECTED
    assert result.position_size is None
    assert any("Invalid sizing configuration" in r for r in result.reasons)


def test_task2a_engine_rejects_missing_balance(dummy_context):
    """Task 2A: Engine rejects at its own guard if balance is missing before reaching any calculator."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(overall_score=90.0, decision=RiskDecision.ALLOW)

    result = engine.calculate_size(
        dummy_context,
        risk,
        entry_price=100.0,
        stop_distance=5.0,
        take_profit_distance=10.0,
        # No account_balance supplied
    )

    assert not result.success
    assert result.status == SizingStatus.REJECTED
    assert result.position_size is None
    assert any("balance" in r.lower() for r in result.reasons + result.violations)
