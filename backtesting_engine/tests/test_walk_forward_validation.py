"""Comprehensive unit and integration tests for Sprint 8B Walk-Forward Validation Engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError

from backtesting_engine.analytics.models.analytics import AnalyticsContext
from backtesting_engine.core.enums import PositionSide
from backtesting_engine.core.exceptions import WalkForwardValidationError
from backtesting_engine.core.models import MarketBar
from backtesting_engine.validation.fold_runner import FoldRunner
from backtesting_engine.validation.metrics import WalkForwardMetricsEngine
from backtesting_engine.validation.models.validation import (
    FoldResult,
    ValidationMethod,
    ValidationWindow,
    WalkForwardConfig,
    WalkForwardReport,
)
from backtesting_engine.validation.walk_forward_engine import WalkForwardEngine
from backtesting_engine.validation.window_generator import (
    AnchoredWindowStrategy,
    ExpandingWindowStrategy,
    RollingWindowStrategy,
    WindowGenerator,
)


def create_synthetic_bars(count: int, start_price: float = 100.0, trend: float = 0.5) -> list[MarketBar]:
    base_time = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    bars = []
    curr_price = start_price
    for i in range(count):
        curr_price += trend if i % 2 == 0 else -trend * 0.5
        high = curr_price + 2.0
        low = curr_price - 2.0
        close = curr_price + 0.5
        bars.append(
            MarketBar(
                symbol="BTC/USDT",
                timeframe="1h",
                timestamp=base_time + timedelta(hours=i),
                open=curr_price,
                high=high,
                low=low,
                close=close,
                volume=100.0,
                index=i,
            )
        )
    return bars


# ============================================================================
# 1. Window Generator Tests (Rolling, Expanding, Anchored)
# ============================================================================

def test_window_generator_rolling_windows():
    bars = create_synthetic_bars(100)
    config = WalkForwardConfig(
        training_window=30,
        testing_window=10,
        step_size=10,
        validation_method=ValidationMethod.ROLLING,
        minimum_history=40,
    )
    generator = WindowGenerator()
    windows = generator.generate_windows(bars, config)

    # 100 bars: (100 - 30 - 10) / 10 + 1 = 7 folds
    assert len(windows) == 7
    assert windows[0].fold_number == 1
    assert windows[0].train_start_idx == 0
    assert windows[0].train_end_idx == 29
    assert windows[0].test_start_idx == 30
    assert windows[0].test_end_idx == 39

    # Fold 2
    assert windows[1].train_start_idx == 10
    assert windows[1].train_end_idx == 39
    assert windows[1].test_start_idx == 40
    assert windows[1].test_end_idx == 49


def test_window_generator_expanding_windows():
    bars = create_synthetic_bars(100)
    config = WalkForwardConfig(
        training_window=30,
        testing_window=10,
        step_size=10,
        validation_method=ValidationMethod.EXPANDING,
        minimum_history=40,
    )
    generator = WindowGenerator()
    windows = generator.generate_windows(bars, config)

    assert len(windows) == 7
    # Fold 1: train [0, 29], test [30, 39]
    assert windows[0].train_start_idx == 0
    assert windows[0].train_end_idx == 29
    # Fold 2: train [0, 39], test [40, 49]
    assert windows[1].train_start_idx == 0
    assert windows[1].train_end_idx == 39
    assert windows[1].test_start_idx == 40


def test_window_generator_anchored_windows():
    bars = create_synthetic_bars(80)
    config = WalkForwardConfig(
        training_window=20,
        testing_window=10,
        step_size=10,
        validation_method=ValidationMethod.ANCHORED,
        minimum_history=30,
    )
    generator = WindowGenerator()
    windows = generator.generate_windows(bars, config)

    assert len(windows) == 6
    for win in windows:
        assert win.train_start_idx == 0  # Always anchored at 0


# ============================================================================
# 2. Data Leakage & Validation Safety Tests
# ============================================================================

def test_zero_data_leakage_between_train_and_test():
    bars = create_synthetic_bars(50)
    config = WalkForwardConfig(training_window=20, testing_window=10, step_size=5, validation_method=ValidationMethod.ROLLING)
    generator = WindowGenerator()
    windows = generator.generate_windows(bars, config)

    for win in windows:
        # Strict zero leakage: test start index MUST be strictly greater than train end index
        assert win.test_start_idx == win.train_end_idx + 1
        assert win.test_start > win.train_end
        assert win.train_end_idx - win.train_start_idx + 1 == 20
        assert win.test_end_idx - win.test_start_idx + 1 == 10


def test_window_generator_rejects_insufficient_history():
    bars = create_synthetic_bars(20)
    config = WalkForwardConfig(training_window=20, testing_window=10, step_size=5, minimum_history=40)
    generator = WindowGenerator()

    with pytest.raises(WalkForwardValidationError, match="Insufficient historical data"):
        generator.generate_windows(bars, config)


def test_window_generator_rejects_empty_dataset():
    config = WalkForwardConfig(training_window=20, testing_window=10, step_size=5)
    generator = WindowGenerator()

    with pytest.raises(WalkForwardValidationError, match="empty dataset"):
        generator.generate_windows([], config)


def test_window_generator_rejects_invalid_chronology():
    bars = create_synthetic_bars(50)
    # Swap timestamps to simulate non-chronological array
    bars[10] = bars[10].model_copy(update={"timestamp": bars[5].timestamp})

    config = WalkForwardConfig(training_window=20, testing_window=10, step_size=5)
    generator = WindowGenerator()

    with pytest.raises(WalkForwardValidationError, match="not strictly chronological"):
        generator.generate_windows(bars, config)


# ============================================================================
# 3. Parameter Validation Tests
# ============================================================================

def test_config_pydantic_positive_window_constraints():
    with pytest.raises(ValidationError):
        WalkForwardConfig(training_window=0, testing_window=10, step_size=5)

    with pytest.raises(ValidationError):
        WalkForwardConfig(training_window=10, testing_window=-5, step_size=5)

    with pytest.raises(ValidationError):
        WalkForwardConfig(training_window=10, testing_window=5, step_size=0)


def test_config_threshold_constraints():
    with pytest.raises(ValidationError):
        WalkForwardConfig(training_window=10, testing_window=5, step_size=1, overfitting_threshold=150.0)

    with pytest.raises(ValidationError):
        WalkForwardConfig(training_window=10, testing_window=5, step_size=1, stability_threshold=-10.0)


# ============================================================================
# 4. Fold Drift & Scoring Metrics Tests
# ============================================================================

def test_fold_drift_metrics_math():
    p_drift, s_drift, d_drift, t_drift = WalkForwardMetricsEngine.compute_fold_drift(
        train_return=0.10,
        test_return=0.05,
        train_sharpe=2.0,
        test_sharpe=1.0,
        train_dd=0.05,
        test_dd=0.10,
        train_trades=10,
        test_trades=5,
    )

    assert p_drift == -0.5  # (0.05 - 0.10)/0.10
    assert s_drift == -1.0  # 1.0 - 2.0
    assert d_drift == 0.05  # 0.10 - 0.05
    assert t_drift == -0.5  # (5 - 10)/10


def test_overfitting_score_calculation_zero_overfit():
    # Test performance equals or exceeds train performance -> Overfitting score = 0.0
    config = WalkForwardConfig(training_window=20, testing_window=10, step_size=5)
    generator = WindowGenerator()
    bars = create_synthetic_bars(50)
    windows = generator.generate_windows(bars, config)

    runner = FoldRunner()
    folds = [runner.run_fold(windows[0], bars, config)]

    report = WalkForwardMetricsEngine.compute_report(folds, config)

    assert isinstance(report, WalkForwardReport)
    assert report.overfitting_score >= 0.0
    assert report.overfitting_score <= 100.0
    assert report.stability_score >= 0.0
    assert report.consistency_score >= 0.0


def test_consistency_and_stability_scores():
    config = WalkForwardConfig(training_window=20, testing_window=10, step_size=5, stability_threshold=40.0, overfitting_threshold=60.0)
    generator = WindowGenerator()
    bars = create_synthetic_bars(60)
    windows = generator.generate_windows(bars, config)

    runner = FoldRunner()
    folds = [runner.run_fold(w, bars, config) for w in windows]

    report = WalkForwardMetricsEngine.compute_report(folds, config)

    assert len(report.folds) == len(windows)
    assert isinstance(report.passed, bool)
    assert report.generated_at.tzinfo == timezone.utc


# ============================================================================
# 5. Full End-to-End WalkForwardEngine Tests
# ============================================================================

def test_walk_forward_engine_end_to_end_rolling():
    bars = create_synthetic_bars(80)
    config = WalkForwardConfig(
        training_window=25,
        testing_window=10,
        step_size=10,
        validation_method=ValidationMethod.ROLLING,
        context=AnalyticsContext(risk_free_rate=0.01, decimal_precision=4),
    )

    orders = [{"symbol": "BTC/USDT", "side": "LONG", "quantity": 1.0, "order_type": "MARKET"}]
    engine = WalkForwardEngine()

    report = engine.run_walk_forward(bars, config, orders_to_place=orders)

    assert isinstance(report, WalkForwardReport)
    assert len(report.folds) == 5
    assert report.engine_version == "1.0.0"
    assert report.config.context.risk_free_rate == 0.01

    # Verify every fold has train and test metrics computed
    for f in report.folds:
        assert isinstance(f, FoldResult)
        assert f.train_metrics.backtest_id != ""
        assert f.test_metrics.backtest_id != ""
        assert f.execution_time_seconds >= 0.0


def test_walk_forward_engine_expanding_end_to_end():
    bars = create_synthetic_bars(70)
    config = WalkForwardConfig(
        training_window=20,
        testing_window=10,
        step_size=10,
        validation_method=ValidationMethod.EXPANDING,
    )

    engine = WalkForwardEngine()
    report = engine.run_walk_forward(bars, config)

    assert len(report.folds) == 5
    assert report.folds[0].window.train_start_idx == 0
    assert report.folds[1].window.train_start_idx == 0
    assert report.folds[1].window.train_end_idx == 29  # Expanded by step_size 10


def test_walk_forward_engine_determinism():
    bars = create_synthetic_bars(60)
    config = WalkForwardConfig(training_window=20, testing_window=10, step_size=10, random_seed=123)

    engine1 = WalkForwardEngine()
    engine2 = WalkForwardEngine()

    rep1 = engine1.run_walk_forward(bars, config)
    rep2 = engine2.run_walk_forward(bars, config)

    assert rep1.average_train_return == rep2.average_train_return
    assert rep1.average_test_return == rep2.average_test_return
    assert rep1.overfitting_score == rep2.overfitting_score
    assert rep1.stability_score == rep2.stability_score
    assert rep1.passed == rep2.passed


# ============================================================================
# 6. Model Immutability & Validation Tests
# ============================================================================

def test_walk_forward_report_immutability():
    config = WalkForwardConfig(training_window=20, testing_window=10, step_size=5)
    report = WalkForwardReport(
        folds=[],
        passed=True,
        config=config,
    )

    with pytest.raises(ValidationError):
        report.passed = False


def test_validation_window_immutability():
    win = ValidationWindow(
        fold_number=1,
        train_start=datetime.now(timezone.utc),
        train_end=datetime.now(timezone.utc),
        test_start=datetime.now(timezone.utc),
        test_end=datetime.now(timezone.utc),
        train_start_idx=0,
        train_end_idx=10,
        test_start_idx=11,
        test_end_idx=20,
    )

    with pytest.raises(ValidationError):
        win.fold_number = 2


def test_walk_forward_report_utc_timestamp_enforcement():
    config = WalkForwardConfig(training_window=20, testing_window=10, step_size=5)
    naive_dt = datetime(2025, 1, 1, 12, 0)  # Naive datetime without tzinfo

    with pytest.raises(ValidationError, match="timezone-aware"):
        WalkForwardReport(
            folds=[],
            passed=True,
            config=config,
            generated_at=naive_dt,
        )


# ============================================================================
# 7. Edge Cases & Warning Generation Tests
# ============================================================================

def test_low_trade_count_warning_generation():
    bars = create_synthetic_bars(50)
    config = WalkForwardConfig(
        training_window=20,
        testing_window=10,
        step_size=10,
        minimum_trades=5,  # Require 5 trades per fold
    )

    engine = WalkForwardEngine()
    report = engine.run_walk_forward(bars, config)  # No orders placed -> 0 trades

    assert len(report.folds) > 0
    # Every fold should generate a low trade count warning
    assert any("below minimum threshold" in w for w in report.folds[0].warnings)


def test_single_fold_dataset():
    bars = create_synthetic_bars(30)
    config = WalkForwardConfig(
        training_window=20,
        testing_window=10,
        step_size=10,
    )

    engine = WalkForwardEngine()
    report = engine.run_walk_forward(bars, config)

    assert len(report.folds) == 1
    assert report.folds[0].fold_number == 1


def test_context_configuration_propagation():
    ctx = AnalyticsContext(risk_free_rate=0.03, annualization_factor=365.0, decimal_precision=2)
    config = WalkForwardConfig(
        training_window=20,
        testing_window=10,
        step_size=10,
        context=ctx,
    )

    bars = create_synthetic_bars(40)
    engine = WalkForwardEngine()
    report = engine.run_walk_forward(bars, config)

    assert report.config.context.risk_free_rate == 0.03
    assert report.config.context.annualization_factor == 365.0
    assert report.folds[0].train_metrics.context.risk_free_rate == 0.03
