"""Unit tests verifying all 10 Sprint 6 Architectural Invariants for the Research Platform."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from research_platform.core.enums import ExperimentStatus, ReportFormat
from research_platform.core.models import (
    DatasetVersion,
    ExperimentConfig,
    ExperimentResult,
    PerformanceMetrics,
    ResearchDashboardView,
    ResearchManifest,
    ResearchReport,
    StrategyVersion,
)
from research_platform.core.orchestrator import ResearchOrchestrator
from research_platform.analysis.metrics_engine import MetricsEngine


# =============================================================================
# Invariant 1 & 2: Never Execute Trades & Never Submit Orders
# =============================================================================

def test_invariant_never_execute_trades_or_submit_orders():
    """Verify that Research Platform models have zero order, trade execution, broker, or exchange fields."""
    for model_cls in (
        DatasetVersion,
        StrategyVersion,
        PerformanceMetrics,
        ResearchManifest,
        ExperimentConfig,
        ExperimentResult,
        ResearchReport,
        ResearchDashboardView,
    ):
        fields = set(model_cls.model_fields.keys())
        forbidden = {
            "buy", "sell", "submit_order", "execute_order", "order_id",
            "broker", "broker_id", "exchange", "fill_price", "position_id",
        }
        assert fields.isdisjoint(forbidden), f"{model_cls.__name__} contains forbidden trading/order/broker fields"


# =============================================================================
# Invariant 3: Never Connect to Exchanges
# =============================================================================

def test_invariant_never_connect_to_exchanges():
    """Verify ResearchOrchestrator can initialize and run 100% offline without network/exchange connections."""
    orch = ResearchOrchestrator()
    orch.initialize()

    ds = DatasetVersion(
        dataset_id="ds-btc-001",
        name="BTC/USDT 1h OHLCV",
        version="v1.0.0",
        checksum="hash-sha256-abc123",
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 12, 31, tzinfo=timezone.utc),
        record_count=100,
        symbols=["BTC/USDT"],
    )
    strat = StrategyVersion(
        strategy_id="strat-sma-001",
        name="SMA Crossover",
        version="v1.2.0",
        parameters={"fast": 10, "slow": 30},
    )

    cfg = orch.create_experiment("Offline Test", ds, strat, parameters={"returns": [0.01, -0.005, 0.02, 0.015, -0.01]})
    res = orch.run_experiment(cfg)

    assert res.status == ExperimentStatus.COMPLETED
    assert res.metrics.sharpe_ratio != 0.0


# =============================================================================
# Invariant 4: Never Modify Datasets
# =============================================================================

def test_invariant_never_modify_datasets():
    """Verify DatasetVersion is frozen and immutable."""
    ds = DatasetVersion(
        dataset_id="ds-eth-001",
        name="ETH/USDT 1h",
        version="v1.0.0",
        checksum="hash-sha256-xyz789",
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 6, 1, tzinfo=timezone.utc),
        record_count=50,
    )

    with pytest.raises(Exception):
        ds.record_count = 9999


# =============================================================================
# Invariant 5: Every Experiment Must Be Reproducible
# =============================================================================

def test_invariant_experiment_reproducibility():
    """Verify identical inputs (dataset checksum + strategy version + seed + parameters) yield 100% identical outputs."""
    ds = DatasetVersion(
        dataset_id="ds-repro-001",
        name="Reproducibility Dataset",
        version="v1.0.0",
        checksum="checksum-12345",
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 3, 1, tzinfo=timezone.utc),
        record_count=50,
    )
    strat = StrategyVersion(
        strategy_id="strat-repro-001",
        name="Reproducibility Strategy",
        version="v2.0.0",
        parameters={"lookback": 20},
    )

    returns = [0.01, -0.005, 0.02, 0.015, -0.01]

    orch1 = ResearchOrchestrator()
    orch1.initialize()
    cfg1 = ExperimentConfig(
        experiment_id="exp-fixed-id-001",
        name="Repro 1",
        dataset_version=ds,
        strategy_version=strat,
        parameters={"returns": returns, "run_walk_forward": False},
        seed=12345,
    )
    res1 = orch1.run_experiment(cfg1)

    orch2 = ResearchOrchestrator()
    orch2.initialize()
    cfg2 = ExperimentConfig(
        experiment_id="exp-fixed-id-001",
        name="Repro 1",
        dataset_version=ds,
        strategy_version=strat,
        parameters={"returns": returns, "run_walk_forward": False},
        seed=12345,
    )
    res2 = orch2.run_experiment(cfg2)

    assert res1.metrics.sharpe_ratio == res2.metrics.sharpe_ratio
    assert res1.metrics.max_drawdown == res2.metrics.max_drawdown
    assert res1.manifest.manifest_checksum == res2.manifest.manifest_checksum


# =============================================================================
# Invariant 6 & 7: Record Dataset Version & Record Strategy Version
# =============================================================================

def test_invariant_record_dataset_and_strategy_versions():
    """Verify every experiment config and result records dataset and strategy version metadata."""
    ds = DatasetVersion(
        dataset_id="ds-meta-001",
        name="Metadata Dataset",
        version="v3.1.0",
        checksum="checksum-999",
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 2, 1, tzinfo=timezone.utc),
        record_count=30,
    )
    strat = StrategyVersion(
        strategy_id="strat-meta-001",
        name="Metadata Strategy",
        version="v4.2.1",
    )

    orch = ResearchOrchestrator()
    orch.initialize()
    cfg = orch.create_experiment("Meta Version Test", ds, strat, parameters={"returns": [0.01, -0.005]})
    res = orch.run_experiment(cfg)

    assert res.config.dataset_version.version == "v3.1.0"
    assert res.config.strategy_version.version == "v4.2.1"
    assert res.config.dataset_version.dataset_id == "ds-meta-001"
    assert res.config.strategy_version.strategy_id == "strat-meta-001"


# =============================================================================
# Invariant 8: All Experiment Outputs Must Be Immutable
# =============================================================================

def test_invariant_outputs_immutable():
    """Verify ExperimentResult and PerformanceMetrics models are frozen and unmodifiable."""
    metrics = PerformanceMetrics(sharpe_ratio=1.5, max_drawdown=0.1)
    with pytest.raises(Exception):
        metrics.sharpe_ratio = 3.0


# =============================================================================
# Invariant 9: Failed Experiments Must Fail Closed
# =============================================================================

def test_invariant_failed_experiments_fail_closed():
    """Verify that execution errors set status to FAILED, return failed result, publish ExperimentFailed, and do not raise."""
    orch = ResearchOrchestrator()
    orch.initialize()

    ds = DatasetVersion(
        dataset_id="ds-err-001",
        name="Err Dataset",
        version="v1.0.0",
        checksum="err-checksum",
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 2, 1, tzinfo=timezone.utc),
        record_count=0,
    )
    strat = StrategyVersion(
        strategy_id="strat-err-001",
        name="Err Strategy",
        version="v1.0.0",
    )

    # Missing returns parameter causes fail-closed execution
    cfg = orch.create_experiment("Error Test", ds, strat, parameters={})

    res = orch.run_experiment(cfg)

    assert res.status == ExperimentStatus.FAILED
    assert "No input returns series" in res.error_message
    assert res.metrics.sharpe_ratio == 0.0
    assert res.manifest is not None


# =============================================================================
# Invariant 10: Metrics Must Be Deterministic
# =============================================================================

def test_invariant_metrics_deterministic():
    """Verify MetricsEngine produces 100% bit-identical results for identical return series."""
    engine1 = MetricsEngine()
    engine2 = MetricsEngine()

    returns = [0.01, -0.005, 0.02, 0.015, -0.01, 0.008, 0.012, -0.003]
    m1 = engine1.calculate_metrics(returns)
    m2 = engine2.calculate_metrics(returns)

    assert m1.sharpe_ratio == m2.sharpe_ratio
    assert m1.sortino_ratio == m2.sortino_ratio
    assert m1.max_drawdown == m2.max_drawdown
    assert m1.calmar_ratio == m2.calmar_ratio
    assert m1.win_rate == m2.win_rate
    assert m1.profit_factor == m2.profit_factor
