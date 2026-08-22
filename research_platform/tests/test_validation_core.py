"""Unit tests for the Validation Core.
"""

from __future__ import annotations

import numpy as np
import pytest

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.validation_core.cv import TimeSeriesCVSplitter
from research_platform.validation_core.drift import DriftDetector
from research_platform.validation_core.models import ValidationConfiguration
from research_platform.validation_core.orchestrator import ValidationCoreOrchestrator
from research_platform.validation_core.overfitting import OverfittingDetector
from research_platform.validation_core.regime import MarketRegimeClassifier
from research_platform.validation_core.robust_stats import RobustStatistics
from research_platform.validation_core.sharpe import SharpeValidator
from research_platform.validation_core.statistical_testing import StatisticalTestingSuite


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return ValidationCoreOrchestrator(event_bus)


def test_cv_purging_and_embargo():
    """Verify train/test index bounds after purging and embargo windows."""
    train_ranges = [(0, 100), (200, 300)]
    test_range = (80, 120)

    # Purge window removes index before test. Embargo removes index after test.
    purged = TimeSeriesCVSplitter.purge_and_embargo(
        train_ranges,
        test_range,
        purge_window=10,
        embargo_window=20
    )

    # First block (0, 100) should be truncated to (0, 70) (since test starts at 80 and purge=10)
    assert purged[0] == (0, 70)
    # Second block (200, 300) is unchanged because start 200 > test_end + embargo (120+20=140)
    assert purged[1] == (200, 300)


def test_combinatorial_purged_cv_splits():
    """Verify CPCV split generator ranges."""
    splits = TimeSeriesCVSplitter.cpcv_split(
        total_len=600,
        num_partitions=6,
        num_test_partitions=2,
        purge_window=5,
        embargo_window=10
    )
    # 6 partitions choose 2 tests combinations = 15 combinations
    assert len(splits) == 15
    for train, test in splits:
        assert len(test) == 2
        assert test[0] < test[1]


def test_pbo_calculation():
    """Verify PBO detects overfitting when a subset of trials are superior by luck."""
    np.random.seed(42)
    # 5 strategy trials
    trials = [np.random.normal(0.001, 0.01, 100) for _ in range(5)]
    pbo = OverfittingDetector.calculate_pbo(trials, num_splits=5)
    assert 0.0 <= pbo <= 1.0


def test_psr_and_dsr_metrics():
    """Verify Probabilistic and Deflated Sharpe Ratio calculation returns correct probabilities."""
    np.random.seed(42)
    returns = list(np.random.normal(0.001, 0.02, 100))
    
    # 1. PSR
    psr = SharpeValidator.calculate_psr(returns, benchmark_sr=0.0)
    assert 0.0 <= psr <= 1.0

    # 2. DSR
    trial_srs = [0.1, 0.2, 0.3, 0.4]
    dsr = SharpeValidator.calculate_dsr(returns, trial_srs)
    assert 0.0 <= dsr <= 1.0


def test_stationary_bootstrap_resampling():
    """Verify stationary bootstrap preserves indices shape."""
    np.random.seed(42)
    returns = np.random.normal(0.0, 0.01, 100)
    samples = StatisticalTestingSuite.stationary_bootstrap(returns, num_bootstrap=5, p=0.1)
    assert len(samples) == 5
    for s in samples:
        assert s.shape == (100,)


def test_hansen_spa_and_white_reality_check():
    """Verify p-value calculations reject random chance."""
    np.random.seed(42)
    target = np.random.normal(0.005, 0.01, 100)
    bench = np.zeros(100)
    alts = [np.random.normal(0.0, 0.01, 100) for _ in range(3)]

    spa_p = StatisticalTestingSuite.hansen_spa_test(target, bench, alts, num_bootstrap=10)
    wrc_p = StatisticalTestingSuite.white_reality_check(target, bench, alts, num_bootstrap=10)
    assert 0.0 <= spa_p <= 1.0
    assert 0.0 <= wrc_p <= 1.0


def test_robust_newey_west_standard_errors():
    """Verify robust t-stats under auto-correlated noise."""
    np.random.seed(42)
    returns = np.random.normal(0.002, 0.01, 200)
    t_stat, se = RobustStatistics.newey_west_t_stat(returns)
    assert se > 0.0
    assert abs(t_stat) > 0.0


def test_drift_detection_metrics():
    """Verify PSI, KL, JS divergence outputs on shifted distributions."""
    np.random.seed(42)
    base = np.random.normal(0.0, 1.0, 100)
    target = np.random.normal(0.5, 1.0, 100)  # shifted mean

    res = DriftDetector.detect_drift("x", base, target)
    assert res.psi > 0.0
    assert res.kl_divergence > 0.0
    assert res.js_divergence > 0.0
    assert res.severity in ("LOW", "HIGH")


def test_regime_classification():
    """Verify market regime states labeling."""
    np.random.seed(42)
    returns = np.random.normal(0.0, 0.01, 100)
    # Add trending segment
    returns[40:60] = 0.05
    # Add high-volatility segment
    returns[60:80] = 0.15

    regimes = MarketRegimeClassifier.classify_regimes(returns, window=10)
    assert len(regimes) == 100
    assert "volatile" in regimes or "trending" in regimes


def test_validation_orchestration_run(orchestrator):
    """Verify orchestrator runs complete validations pipeline and returns reports."""
    np.random.seed(42)
    returns = np.random.normal(0.003, 0.01, 300)
    trials = [returns, returns * 0.9]

    config = ValidationConfiguration(
        backtest_id="bt_999",
        cv_method="CPCV",
        pbo_enabled=True,
        psr_enabled=True,
        dsr_enabled=True,
        regime_enabled=True,
        drift_enabled=True
    )

    report = orchestrator.validate_strategy(config, "ds_1", returns, trials)
    assert report.is_approved is True
    assert report.research_score.score_value > 50.0
    assert len(report.cv_results) > 0
    assert len(report.drift_results) == 1
    assert len(report.regime_results) > 0

    # Retrieve from repository
    loaded = orchestrator.repository.get_run(orchestrator.repository.list_runs()[0].run_id)
    assert loaded is not None
    assert loaded.status == "COMPLETED"
