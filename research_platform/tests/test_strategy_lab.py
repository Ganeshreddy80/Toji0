"""Unit tests for the Strategy Lab.
"""

from __future__ import annotations

import uuid
import pandas as pd
import pytest

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.alpha_factory.models import AlphaCandidate, AlphaExpression
from research_platform.strategy_lab.builder import StrategyBuilder
from research_platform.strategy_lab.models import (
    EntryRule,
    ExitRule,
    PositionSizingRule,
    RiskRule,
    StrategyDefinition
)
from research_platform.strategy_lab.orchestrator import StrategyLabOrchestrator
from research_platform.strategy_lab.position_sizing import PositionSizer
from research_platform.strategy_lab.rules import RuleEvaluator


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return StrategyLabOrchestrator(event_bus)


def test_rule_evaluator_triggers():
    """Verify entry and exit rule evaluations."""
    df = pd.DataFrame({
        "close": [10.0, 11.0, 12.0, 11.5, 13.0],
        "fast": [1.0, 2.0, 3.0, 4.0, 5.0],
        "slow": [1.5, 2.5, 2.8, 3.2, 5.2]
    })

    # 1. Threshold Entry
    res_thresh = RuleEvaluator.evaluate_entry(
        condition_type="SignalThreshold",
        params={"column": "close", "threshold": 11.0, "operator": ">"},
        df=df
    )
    # close > 11: should be true for index 2, 3, 4
    assert res_thresh.iloc[0] == False
    assert res_thresh.iloc[2] == True

    # 2. Crossover Entry
    res_cross = RuleEvaluator.evaluate_entry(
        condition_type="Crossover",
        params={"fast_column": "fast", "slow_column": "slow"},
        df=df
    )
    # fast crossed slow at index 2 (fast 3.0 > slow 2.8 and fast_1 2.0 <= slow_1 2.5)
    assert res_cross.iloc[1] == False
    assert res_cross.iloc[2] == True

    # 3. Stop Loss Exit
    # entry_price 10.0, price at index 3 is 11.5 -> stop_price for 10% stop is 9.0 -> False
    exit_sl = RuleEvaluator.evaluate_exit(
        condition_type="StopLoss",
        params={"stop_pct": 0.10},
        df=df,
        entry_price=10.0,
        current_idx=3
    )
    assert exit_sl == False

    # price drops to 8.0 -> True
    df_drop = pd.DataFrame({"close": [10.0, 8.0]})
    exit_sl_drop = RuleEvaluator.evaluate_exit(
        condition_type="StopLoss",
        params={"stop_pct": 0.10},
        df=df_drop,
        entry_price=10.0,
        current_idx=1
    )
    assert exit_sl_drop == True


def test_position_sizing_allocations():
    """Verify units sizing calculations."""
    # 1. Fixed Fractional (risk 2% of capital, 2% stop per share)
    units_frac = PositionSizer.calculate_size(
        sizing_type="FixedFractional",
        params={"fraction": 0.02, "stop_pct": 0.02},
        capital=100000.0,
        price=100.0
    )
    # risk_amt = 2000, risk_per_share = 2. Units = 2000 / 2 = 1000
    assert units_frac == pytest.approx(1000.0)

    # 2. Kelly Criterion sizing
    units_kelly = PositionSizer.calculate_size(
        sizing_type="Kelly",
        params={"win_probability": 0.60, "win_loss_ratio": 1.0, "kelly_fraction": 0.5},
        capital=100000.0,
        price=100.0
    )
    # Kelly fraction: (0.6 * 1 - 0.4) / 1 = 0.20
    # half-Kelly: 0.10 of capital = 10000. Units = 10000 / 100 = 100
    assert units_kelly == pytest.approx(100.0)


def test_alpha_to_strategy_builder():
    """Verify StrategyBuilder converter wraps AlphaCandidate properties."""
    expr = AlphaExpression(expression_id="1", formula_str="close")
    alpha = AlphaCandidate(candidate_id="cand_abc", expression=expr, author="Quant")

    strat = StrategyBuilder.convert_alpha_to_strategy(alpha)
    assert strat.name == "Strategy_cand_abc"
    assert strat.entry_rules[0].parameters["column"] == "alpha_cand_abc"
    assert len(strat.exit_rules) == 2


def test_orchestration_composition_and_export(orchestrator):
    """Verify composition audits, state validation, and backtest export."""
    entry = EntryRule(name="Entry", condition_type="SignalThreshold", parameters={"column": "close", "threshold": 10.0})
    exit_rule = ExitRule(name="Exit", condition_type="StopLoss", parameters={"stop_pct": 0.02})
    sizing = PositionSizingRule(name="Size", sizing_type="FixedSize", parameters={"units": 10})
    risk = RiskRule(name="Risk", limit_type="MaxRiskPerTrade", value=0.02)  # Valid risk limit

    strat_def = StrategyDefinition(
        strategy_id="strat_123",
        name="TestStrategy",
        display_name="Test Strategy",
        description="Description",
        version="1.0.0",
        entry_rules=[entry],
        exit_rules=[exit_rule],
        sizing_rule=sizing,
        risk_rules=[risk]
    )

    # 1. Successful composition
    validated = orchestrator.compose_strategy(strat_def)
    assert validated.status == "VALIDATED"
    assert orchestrator.registry.get("strat_123") is not None

    # 2. Risk violation rejection (RiskRule value 10% exceeds trade cap)
    invalid_risk = RiskRule(name="Risk", limit_type="MaxRiskPerTrade", value=0.10)
    strat_def_invalid = StrategyDefinition(
        strategy_id="strat_999",
        name="InvalidStrategy",
        display_name="Invalid Strategy",
        description="Description",
        version="1.0.0",
        entry_rules=[entry],
        exit_rules=[exit_rule],
        sizing_rule=sizing,
        risk_rules=[invalid_risk]
    )

    with pytest.raises(ValueError):
        orchestrator.compose_strategy(strat_def_invalid)

    # 3. Successful backtest export promotion
    exported = orchestrator.export_to_backtest("strat_123")
    assert exported.status == "APPROVED"
