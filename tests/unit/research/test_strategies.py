"""Unit tests for quantitative strategy models and rule definitions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from research.strategies.models import (
    EntryRule,
    ExitRule,
    RiskRule,
    PositionSizingRule,
    MarketFilter,
    Strategy,
)


def test_strategy_rules_instantiation():
    """Verify strategy rules instantiate correctly with typical fields."""
    entry = EntryRule(
        name="RSI Oversold",
        condition_expr="rsi < 30",
        parameters={"rsi_period": 14, "rsi_limit": 30},
    )
    assert entry.name == "RSI Oversold"
    assert entry.condition_expr == "rsi < 30"
    assert entry.parameters["rsi_period"] == 14

    exit_rule = ExitRule(
        name="RSI Overbought",
        condition_expr="rsi > 70",
        parameters={"rsi_limit": 70},
    )
    assert exit_rule.name == "RSI Overbought"

    risk = RiskRule(
        name="ATR Stop Loss",
        condition_expr="price < entry_price - 2 * atr",
        parameters={"atr_multiplier": 2.0},
    )
    assert risk.parameters["atr_multiplier"] == 2.0

    sizing = PositionSizingRule(
        name="Kelly Sizing",
        condition_expr="kelly_ratio * equity",
        parameters={"kelly_fraction": 0.5},
    )
    assert sizing.parameters["kelly_fraction"] == 0.5

    mkt_filter = MarketFilter(
        name="Regime Filter",
        condition_expr="regime == 'trending'",
        parameters={"min_trend_strength": 20},
    )
    assert mkt_filter.parameters["min_trend_strength"] == 20


def test_strategy_rules_are_frozen():
    """Verify rule models are frozen (read-only)."""
    entry = EntryRule(name="RSI", condition_expr="rsi < 30")
    with pytest.raises(ValidationError):
        entry.name = "New Rule Name"  # type: ignore


def test_strategy_instantiation():
    """Verify a complete strategy instantiates correctly with rules and dependencies."""
    entry = EntryRule(name="Entry", condition_expr="close > ema")
    exit_rule = ExitRule(name="Exit", condition_expr="close < ema")
    risk = RiskRule(name="StopLoss", condition_expr="drawdown > 0.05")
    sizing = PositionSizingRule(name="FixedRisk", condition_expr="0.02 * equity")
    mkt_filter = MarketFilter(name="VolFilter", condition_expr="vol < max_vol")

    strategy = Strategy(
        strategy_id="strat-999",
        name="TrendFollowingEMA",
        version="1.1.0",
        experiment_id="exp-456",
        entry_rules=[entry],
        exit_rules=[exit_rule],
        risk_rules=[risk],
        position_sizing_rules=[sizing],
        market_filters=[mkt_filter],
        metadata={"author": "QuantTeam", "asset_class": "crypto"},
    )

    assert strategy.strategy_id == "strat-999"
    assert strategy.name == "TrendFollowingEMA"
    assert strategy.version == "1.1.0"
    assert strategy.experiment_id == "exp-456"
    assert len(strategy.entry_rules) == 1
    assert strategy.entry_rules[0].name == "Entry"
    assert len(strategy.exit_rules) == 1
    assert len(strategy.risk_rules) == 1
    assert len(strategy.position_sizing_rules) == 1
    assert len(strategy.market_filters) == 1
    assert strategy.metadata["author"] == "QuantTeam"


def test_strategy_immutable():
    """Verify Strategy model is frozen."""
    strategy = Strategy(
        strategy_id="strat-1",
        name="Test",
        experiment_id="exp-1",
    )
    with pytest.raises(ValidationError):
        strategy.name = "Changed"  # type: ignore
