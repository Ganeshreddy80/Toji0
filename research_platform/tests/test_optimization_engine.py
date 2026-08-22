"""Unit tests for the Optimization Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd
import pytest

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.backtesting_engine.orchestrator import BacktestingEngineOrchestrator
from research_platform.optimization_engine.space import ParameterSpaceSampler
from research_platform.optimization_engine.algorithms import (
    GeneticAlgorithmOptimizer,
    GridSearchOptimizer,
    RandomSearchOptimizer
)
from research_platform.optimization_engine.models import (
    OptimizationConfiguration,
    OptimizationTrial,
    ParameterDefinition,
    ParameterSpace,
    ParameterCombination,
    ObjectiveScore,
    ConstraintResult
)
from research_platform.optimization_engine.orchestrator import OptimizationEngineOrchestrator
from research_platform.optimization_engine.robustness import RobustnessAnalyzer
from research_platform.optimization_engine.walk_forward import WalkForwardOptimizer
from research_platform.strategy_lab.models import EntryRule, ExitRule, PositionSizingRule, StrategyDefinition


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def backtester(event_bus):
    return BacktestingEngineOrchestrator(event_bus)


@pytest.fixture
def orchestrator(event_bus, backtester):
    return OptimizationEngineOrchestrator(event_bus, backtester)


def test_parameter_space_sampling():
    """Verify ParameterSpace discrete step limits and LHS bins shuffle."""
    p1 = ParameterDefinition(name="fast", type="int", bounds=[10.0, 20.0])
    p2 = ParameterDefinition(name="slow", type="float", bounds=[30.0, 50.0])
    p3 = ParameterDefinition(name="mode", type="categorical", categorical_values=["bullish", "bearish"])
    
    space = ParameterSpace(parameters=[p1, p2, p3])

    # 1. Grid Sampling
    grid = ParameterSpaceSampler.sample_grid(space, steps=2)
    assert len(grid) > 0
    # Ensure parameter boundaries are met
    first = grid[0].values
    assert 10 <= first["fast"] <= 20
    assert 30.0 <= first["slow"] <= 50.0

    # 2. LHS Sampling
    lhs = ParameterSpaceSampler.sample_lhs(space, num_samples=5)
    assert len(lhs) == 5
    assert "fast" in lhs[0].values


def test_optimizer_algorithms():
    """Verify optimizer interfaces generate combinations."""
    p = ParameterDefinition(name="val", type="float", bounds=[0.0, 1.0])
    space = ParameterSpace(parameters=[p])
    config = OptimizationConfiguration(space=space, num_trials=10)

    grid_opt = GridSearchOptimizer()
    grid_combos = grid_opt.generate_combinations(config)
    assert len(grid_combos) <= 10

    rand_opt = RandomSearchOptimizer()
    rand_combos = rand_opt.generate_combinations(config)
    assert len(rand_combos) == 10


def test_walk_forward_window_splits():
    """Verify train/test rolling window intervals."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 1, tzinfo=timezone.utc)

    # 90 train days, 30 test days, 30 step days -> should generate multiple windows
    windows = WalkForwardOptimizer.generate_windows(start, end, train_days=90, test_days=30, step_days=30)
    assert len(windows) > 0
    assert windows[0].train_start == start
    # first window test start = 90 days after start
    assert (windows[0].test_start - windows[0].train_start).days == 90
    assert (windows[0].test_end - windows[0].test_start).days == 30


def test_robustness_analysis():
    """Verify neighborhood stability checks."""
    trials = []
    # Trial scores simulating a peaked parabolic response curve: best val at 0.5
    for val in [0.1, 0.2, 0.5, 0.8, 0.9]:
        combo = ParameterCombination(values={"param": val})
        score = ObjectiveScore(metrics={}, composite_score=10.0 - abs(0.5 - val) * 10.0)
        trials.append(
            OptimizationTrial(
                trial_id=f"t_{val}",
                parameters=combo,
                score=score,
                is_valid=True,
                constraint_result=ConstraintResult(is_violated=False, details="")
            )
        )

    metrics = RobustnessAnalyzer.evaluate_parameter("param", trials)
    assert metrics.neighborhood_standard_deviation > 0.0
    assert 0.0 < metrics.parameter_stability_score <= 1.0


def test_optimization_orchestration(orchestrator):
    """Verify execution loops evaluate parameter sweeps and rank Pareto fronts."""
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-06-25 12:00:00", periods=20, freq="1min"),
        "open": [10.0 + i for i in range(20)],
        "high": [10.5 + i for i in range(20)],
        "low": [9.5 + i for i in range(20)],
        "close": [10.2 + i for i in range(20)],
        "volume": [1000.0 for _ in range(20)]
    })

    # Strategy Definition
    entry = EntryRule(name="Entry", condition_type="SignalThreshold", parameters={"column": "close", "threshold": 12.0})
    exit_rule = ExitRule(name="Exit", condition_type="ProfitTarget", parameters={"target_pct": 0.20})
    sizing = PositionSizingRule(name="Sizing", sizing_type="FixedSize", parameters={"units": 1})
    
    strategy = StrategyDefinition(
        strategy_id="strat_opt",
        name="SweepStrategy",
        display_name="Sweep Strategy",
        description="Desc",
        version="1.0.0",
        entry_rules=[entry],
        exit_rules=[exit_rule],
        sizing_rule=sizing,
        risk_rules=[]
    )

    # Search space: optimize threshold
    p = ParameterDefinition(name="threshold", type="float", bounds=[10.0, 15.0])
    space = ParameterSpace(parameters=[p])

    config = OptimizationConfiguration(
        space=space,
        objective_weights={"Sharpe": 1.0},
        algorithm="GRID",
        num_trials=3
    )

    res = orchestrator.run_optimization(
        config=config,
        data_df=df,
        strategy=strategy,
        start_time=datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 25, 12, 19, 0, tzinfo=timezone.utc)
    )

    assert res.best_trial is not None
    assert len(res.pareto_front.non_dominated_trials) > 0
    assert len(orchestrator.repository.list_runs()) == 1
