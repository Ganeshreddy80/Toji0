"""Comprehensive Test Suite for Sprint 8C Monte Carlo Simulation Engine (Hardened)."""

from datetime import datetime, timezone
import importlib
import sys
import time

import numpy as np

from pydantic import ValidationError
import pytest

from backtesting_engine.core.enums import PositionSide, ReplayStatus, TradeStatus
from backtesting_engine.core.models import (
    BacktestConfig,
    BacktestResult,
    EquityPoint,
    TradeRecord,
)
from backtesting_engine.monte_carlo.bootstrap import (
    BlockBootstrap,
    ReturnBootstrap,
    TradeBootstrap,
)
from backtesting_engine.monte_carlo.confidence import MonteCarloConfidenceEngine
from backtesting_engine.monte_carlo.models.monte_carlo import (
    BootstrapMethod,
    ConfidenceInterval,
    MonteCarloConfig,
    MonteCarloReport,
    SimulationResult,
)
from backtesting_engine.monte_carlo.orchestrator import MonteCarloOrchestrator
from backtesting_engine.monte_carlo.risk import MonteCarloRiskEngine
from backtesting_engine.monte_carlo.simulator import MonteCarloSimulator
from backtesting_engine.monte_carlo.statistics import MonteCarloStatisticsEngine


@pytest.fixture
def sample_backtest_config():
    return BacktestConfig(
        backtest_id="bt-mc-test-01",
        name="Monte Carlo Test Run",
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
        initial_capital=100000.0,
    )


@pytest.fixture
def winning_backtest_result(sample_backtest_config):
    trades = [
        TradeRecord(
            order_id=f"ord-{i}",
            symbol="BTC/USDT",
            side=PositionSide.LONG,
            entry_price=50000.0,
            exit_price=52000.0,
            quantity=1.0,
            realized_pnl=2000.0,
            status=TradeStatus.CLOSED,
        )
        for i in range(20)
    ]
    returns_series = [0.02] * 20
    equity_curve = [100000.0 + i * 2000.0 for i in range(21)]
    return BacktestResult(
        backtest_id="bt-win-01",
        config=sample_backtest_config,
        replay_session_id="session-win-01",
        status=ReplayStatus.COMPLETED,
        returns_series=returns_series,
        equity_curve=equity_curve,
        trades=trades,
        final_equity=140000.0,
    )


@pytest.fixture
def losing_backtest_result(sample_backtest_config):
    trades = [
        TradeRecord(
            order_id=f"ord-loss-{i}",
            symbol="BTC/USDT",
            side=PositionSide.LONG,
            entry_price=50000.0,
            exit_price=25000.0,
            quantity=1.0,
            realized_pnl=-25000.0,
            status=TradeStatus.CLOSED,
        )
        for i in range(15)
    ]
    returns_series = [-0.25] * 15
    equity_curve = [100000.0 - i * 25000.0 for i in range(5)]
    return BacktestResult(
        backtest_id="bt-loss-01",
        config=sample_backtest_config,
        replay_session_id="session-loss-01",
        status=ReplayStatus.COMPLETED,
        returns_series=returns_series,
        equity_curve=equity_curve,
        trades=trades,
        final_equity=0.0,
    )


# 1. Bootstrap correctness (F-07 strengthened)
def test_bootstrap_correctness():
    rng = np.random.default_rng(42)
    data = np.array([0.01, -0.02, 0.03, -0.01, 0.05])

    tb = TradeBootstrap()
    res_tb = tb.resample(data, num_paths=10, path_length=5, rng=rng)
    assert res_tb.shape == (10, 5)
    for elem in res_tb.ravel():
        assert elem in data

    rb = ReturnBootstrap()
    res_rb = rb.resample(data, num_paths=10, path_length=5, rng=rng)
    assert res_rb.shape == (10, 5)
    for elem in res_rb.ravel():
        assert elem in data

    bb = BlockBootstrap(block_size=3)
    res_bb = bb.resample(data, num_paths=10, path_length=6, rng=rng)
    assert res_bb.shape == (10, 6)
    for elem in res_bb.ravel():
        assert elem in data


# 2. Deterministic output
def test_deterministic_output(winning_backtest_result):
    config = MonteCarloConfig(iterations=200, random_seed=42, deterministic=True)
    orchestrator = MonteCarloOrchestrator()

    report1 = orchestrator.run(winning_backtest_result, config)
    report2 = orchestrator.run(winning_backtest_result, config)

    assert report1.expected_return == report2.expected_return
    assert report1.expected_drawdown == report2.expected_drawdown
    assert report1.risk_of_ruin == report2.risk_of_ruin
    for s1, s2 in zip(report1.simulations, report2.simulations):
        assert s1.ending_equity == s2.ending_equity
        assert s1.max_drawdown == s2.max_drawdown


# 3. Confidence interval math (F-09 strengthened)
def test_confidence_interval_math(winning_backtest_result):
    config = MonteCarloConfig(iterations=500, random_seed=42, confidence_levels=[0.90, 0.95, 0.99])
    orchestrator = MonteCarloOrchestrator()
    report = orchestrator.run(winning_backtest_result, config)

    assert len(report.confidence_intervals) == 15  # 5 metrics * 3 levels
    sim_returns = np.array([s.total_return for s in report.simulations])

    # Verify actual percentile math for Return CIs
    ci_90 = [ci for ci in report.confidence_intervals if ci.metric == "Return" and ci.confidence_level == 0.90][0]
    expected_lower = float(np.percentile(sim_returns, 5.0))
    expected_upper = float(np.percentile(sim_returns, 95.0))
    assert pytest.approx(ci_90.lower_bound) == expected_lower
    assert pytest.approx(ci_90.upper_bound) == expected_upper


# 4. Percentile calculation
def test_percentile_calculation():
    engine = MonteCarloStatisticsEngine()
    sims = [
        SimulationResult(
            iteration=i,
            ending_equity=100000.0 + i * 1000.0,
            max_drawdown=0.01 * i,
            total_return=0.01 * i,
            cagr=0.01 * i,
            sharpe=1.0 + 0.1 * i,
            ruin=False,
        )
        for i in range(100)
    ]
    stats = engine.compute_statistics(sims)
    pt = stats["percentile_table"]

    assert "1%" in pt and "50%" in pt and "99%" in pt
    assert pt["1%"]["total_return"] <= pt["50%"]["total_return"] <= pt["99%"]["total_return"]


# 5. Risk of ruin (F-08 strengthened)
def test_risk_of_ruin(losing_backtest_result):
    config = MonteCarloConfig(iterations=200, random_seed=42, ruin_threshold_pct=0.50)
    orchestrator = MonteCarloOrchestrator()
    report = orchestrator.run(losing_backtest_result, config)

    assert report.risk_of_ruin > 0.0
    assert report.summary["probability_of_loss"] == 1.0


# 6. Empty backtest
def test_empty_backtest(sample_backtest_config):
    empty_result = BacktestResult(
        backtest_id="bt-empty-01",
        config=sample_backtest_config,
        replay_session_id="session-empty",
        status=ReplayStatus.COMPLETED,
        returns_series=[],
        equity_curve=[100000.0],
        trades=[],
        final_equity=100000.0,
    )
    orchestrator = MonteCarloOrchestrator()
    report = orchestrator.run(empty_result)

    assert len(report.simulations) == 1000
    for s in report.simulations:
        assert s.ending_equity == 100000.0
        assert s.total_return == 0.0
        assert s.max_drawdown == 0.0
        assert s.ruin is False


# 7. Single trade
def test_single_trade(sample_backtest_config):
    trade = TradeRecord(
        order_id="ord-single",
        symbol="BTC/USDT",
        side=PositionSide.LONG,
        entry_price=50000.0,
        exit_price=55000.0,
        quantity=1.0,
        realized_pnl=5000.0,
        status=TradeStatus.CLOSED,
    )
    single_result = BacktestResult(
        backtest_id="bt-single-01",
        config=sample_backtest_config,
        replay_session_id="session-single",
        status=ReplayStatus.COMPLETED,
        returns_series=[0.05],
        equity_curve=[100000.0, 105000.0],
        trades=[trade],
        final_equity=105000.0,
    )
    orchestrator = MonteCarloOrchestrator()
    report = orchestrator.run(single_result, MonteCarloConfig(iterations=100))

    assert len(report.simulations) == 100
    assert report.expected_return > 0.0


# 8. Losing strategy
def test_losing_strategy(losing_backtest_result):
    orchestrator = MonteCarloOrchestrator()
    report = orchestrator.run(losing_backtest_result, MonteCarloConfig(iterations=200))

    assert report.expected_return < 0.0
    assert report.summary["probability_of_loss"] == 1.0


# 9. Winning strategy
def test_winning_strategy(winning_backtest_result):
    orchestrator = MonteCarloOrchestrator()
    report = orchestrator.run(winning_backtest_result, MonteCarloConfig(iterations=200))

    assert report.expected_return > 0.0
    assert report.summary["probability_of_profit"] == 1.0
    assert report.risk_of_ruin == 0.0


# 10. Large iteration performance (F-01 verified)
def test_large_iteration_performance(winning_backtest_result):
    orchestrator = MonteCarloOrchestrator()

    for method in [BootstrapMethod.TRADE, BootstrapMethod.RETURN, BootstrapMethod.BLOCK]:
        config = MonteCarloConfig(iterations=10000, bootstrap_method=method, random_seed=42)
        start_time = time.perf_counter()
        report = orchestrator.run(winning_backtest_result, config)
        elapsed = time.perf_counter() - start_time

        assert len(report.simulations) == 10000
        assert elapsed < 5.0


# 11. Seed reproducibility
def test_seed_reproducibility(winning_backtest_result):
    orchestrator = MonteCarloOrchestrator()

    report_seed42_a = orchestrator.run(winning_backtest_result, MonteCarloConfig(iterations=300, random_seed=42))
    report_seed42_b = orchestrator.run(winning_backtest_result, MonteCarloConfig(iterations=300, random_seed=42))
    report_seed99 = orchestrator.run(winning_backtest_result, MonteCarloConfig(iterations=300, random_seed=99))

    assert report_seed42_a.expected_return == report_seed42_b.expected_return
    assert report_seed42_a.expected_return != report_seed99.expected_return


# 12. Immutable models
def test_immutable_models():
    config = MonteCarloConfig(iterations=100)
    with pytest.raises((ValidationError, TypeError)):
        config.iterations = 200

    sim_res = SimulationResult(
        iteration=0,
        ending_equity=100000.0,
        max_drawdown=0.1,
        total_return=0.05,
        cagr=0.05,
        sharpe=1.2,
        ruin=False,
    )
    with pytest.raises((ValidationError, TypeError)):
        sim_res.ending_equity = 200000.0

    ci = ConfidenceInterval(metric="Return", confidence_level=0.95, lower_bound=0.01, upper_bound=0.10)
    with pytest.raises((ValidationError, TypeError)):
        ci.lower_bound = 0.02


# 13. Invalid configuration
def test_invalid_configuration():
    with pytest.raises((ValidationError, ValueError)):
        MonteCarloConfig(confidence_levels=[1.5])

    with pytest.raises((ValidationError, ValueError)):
        MonteCarloConfig(block_size=0)


# 14. Zero iterations
def test_zero_iterations(winning_backtest_result):
    with pytest.raises((ValidationError, ValueError)):
        MonteCarloConfig(iterations=0)

    orchestrator = MonteCarloOrchestrator()
    invalid_config = MonteCarloConfig.model_construct(iterations=0)
    with pytest.raises(ValueError, match="iterations must be > 0"):
        orchestrator.run(winning_backtest_result, config=invalid_config)


# 15. Statistical correctness (F-04 consistency test)
def test_statistical_correctness():
    arr = np.array([10.0, 12.0, 23.0, 23.0, 16.0, 23.0, 21.0, 16.0])
    stats = MonteCarloStatisticsEngine.compute_array_stats(arr)

    assert stats["mean"] == pytest.approx(18.0)
    assert stats["median"] == pytest.approx(18.5)
    assert stats["variance"] == pytest.approx(np.var(arr, ddof=1))
    assert stats["std"] == pytest.approx(np.std(arr, ddof=1))

    # Verify mathematical consistency of central moments
    diffs = arr - 18.0
    m2 = float(np.mean(diffs**2))
    m3 = float(np.mean(diffs**3))
    m4 = float(np.mean(diffs**4))
    assert stats["skewness"] == pytest.approx(m3 / (m2**1.5))
    assert stats["kurtosis"] == pytest.approx((m4 / (m2**2)) - 3.0)


# 16. Distribution stability (F-10 tightened)
def test_distribution_stability(winning_backtest_result):
    orchestrator = MonteCarloOrchestrator()

    report_100 = orchestrator.run(winning_backtest_result, MonteCarloConfig(iterations=100, random_seed=42))
    report_5000 = orchestrator.run(winning_backtest_result, MonteCarloConfig(iterations=5000, random_seed=42))

    assert pytest.approx(report_100.expected_return, abs=0.02) == report_5000.expected_return


# 17. Regression compatibility
def test_regression_compatibility(sample_backtest_config):
    snapshots = [
        EquityPoint(
            timestamp=datetime(2025, 1, i + 1, tzinfo=timezone.utc),
            balance=100000.0 + i * 100,
            equity=100000.0 + i * 100,
            drawdown=0.0,
            open_pnl=0.0,
            closed_pnl=i * 100,
            account_value=100000.0 + i * 100,
        )
        for i in range(10)
    ]
    res = BacktestResult(
        backtest_id="bt-compat-01",
        config=sample_backtest_config,
        replay_session_id="session-compat",
        status=ReplayStatus.COMPLETED,
        returns_series=[],
        equity_snapshots=snapshots,
        final_equity=100900.0,
    )
    orchestrator = MonteCarloOrchestrator()
    report = orchestrator.run(res, MonteCarloConfig(bootstrap_method=BootstrapMethod.RETURN, iterations=50))

    assert len(report.simulations) == 50


# 18. No architecture violations
def test_no_architecture_violations():
    mc_module = importlib.import_module("backtesting_engine.monte_carlo")
    forbidden_terms = ["execution_engine", "market_gateway", "paper_trading", "strategy"]

    for name in dir(mc_module):
        obj = getattr(mc_module, name)
        module_name = getattr(obj, "__module__", "")
        for forbidden in forbidden_terms:
            assert forbidden not in module_name


# 19. block_size override test (F-02)
def test_block_size_override(winning_backtest_result):
    simulator = MonteCarloSimulator(config=MonteCarloConfig(bootstrap_method=BootstrapMethod.BLOCK, block_size=2))
    override_cfg = MonteCarloConfig(bootstrap_method=BootstrapMethod.BLOCK, block_size=10, random_seed=42)

    sims_override = simulator.simulate(winning_backtest_result, config_override=override_cfg)
    assert len(sims_override) == 1000


# 20. preserve_trade_order test (F-03)
def test_preserve_trade_order():
    rng = np.random.default_rng(42)
    data = np.array([0.01, 0.02, 0.03, 0.04, 0.05])

    tb_unordered = TradeBootstrap(preserve_trade_order=False)
    tb_ordered = TradeBootstrap(preserve_trade_order=True)

    res_un = tb_unordered.resample(data, num_paths=5, path_length=5, rng=np.random.default_rng(42))
    res_ord = tb_ordered.resample(data, num_paths=5, path_length=5, rng=np.random.default_rng(42))

    # Verify that in res_ord, each path is a circular shift preserving consecutive trade order
    for row in res_ord:
        diffs = (row[1:] - row[:-1])
        # Consecutive elements in original data differ by 0.01 or wrap around from 0.05 to 0.01 (-0.04)
        for d in diffs:
            assert pytest.approx(d) == 0.01 or pytest.approx(d) == -0.04


# 21. deterministic flag test (F-05)
def test_deterministic_flag(winning_backtest_result):
    simulator = MonteCarloSimulator()
    cfg_non_det = MonteCarloConfig(iterations=50, deterministic=False, random_seed=None)

    res1 = simulator.simulate(winning_backtest_result, config_override=cfg_non_det)
    res2 = simulator.simulate(winning_backtest_result, config_override=cfg_non_det)

    # Non-deterministic runs with random_seed=None produce different equity paths
    assert res1[0].ending_equity != res2[0].ending_equity or res1[1].ending_equity != res2[1].ending_equity
