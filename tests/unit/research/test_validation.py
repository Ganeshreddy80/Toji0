"""Unit tests for quantitative strategy validation engines."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.strategies.models import Strategy
from research.validation.engines import (
    WalkForwardValidator,
    CrossValidator,
    OutOfSampleValidator,
    StatisticalSignificanceTester,
    RobustnessTester,
)


@pytest.fixture
def dummy_strategy() -> Strategy:
    """Fixture for a dummy strategy model."""
    return Strategy(
        strategy_id="strat-test",
        name="Test Strategy",
        experiment_id="exp-test",
    )


@pytest.fixture
def rising_market_data() -> pd.DataFrame:
    """Fixture generating a pandas DataFrame of steadily rising prices."""
    dates = pd.date_range(start="2026-01-01", periods=100, freq="D")
    prices = np.linspace(100.0, 200.0, 100)
    return pd.DataFrame({"close": prices}, index=dates)


@pytest.fixture
def falling_market_data() -> pd.DataFrame:
    """Fixture generating a pandas DataFrame of steadily falling prices."""
    dates = pd.date_range(start="2026-01-01", periods=100, freq="D")
    prices = np.linspace(200.0, 100.0, 100)
    return pd.DataFrame({"close": prices}, index=dates)


def test_walk_forward_validator(dummy_strategy: Strategy, rising_market_data: pd.DataFrame):
    """Test WalkForwardValidator splits and validation logic."""
    validator = WalkForwardValidator(windows=3, train_ratio=0.8)
    assert validator.name == "Walk-Forward Validation"

    result = validator.validate(dummy_strategy, rising_market_data)
    assert isinstance(result.passed, bool)
    assert "passed_ratio" in result.metrics
    assert "windows" in result.details
    assert len(result.details["windows"]) == 3


def test_walk_forward_validator_insufficient_data(dummy_strategy: Strategy):
    """Test WalkForwardValidator with too few data points."""
    validator = WalkForwardValidator()
    short_data = pd.DataFrame({"close": [10.0, 11.0, 12.0]})
    result = validator.validate(dummy_strategy, short_data)
    assert result.passed is False


def test_cross_validator(dummy_strategy: Strategy, rising_market_data: pd.DataFrame):
    """Test CrossValidator splits and verification."""
    validator = CrossValidator(folds=4)
    assert validator.name == "Time Series Cross Validation"

    result = validator.validate(dummy_strategy, rising_market_data)
    assert isinstance(result.passed, bool)
    assert "mean_sharpe" in result.metrics
    assert len(result.details["folds_sharpe"]) == 4


def test_cross_validator_insufficient_data(dummy_strategy: Strategy):
    """Test CrossValidator with insufficient data."""
    validator = CrossValidator()
    result = validator.validate(dummy_strategy, pd.DataFrame())
    assert result.passed is False


def test_out_of_sample_validator(dummy_strategy: Strategy, rising_market_data: pd.DataFrame):
    """Test OutOfSampleValidator metrics calculation."""
    validator = OutOfSampleValidator(train_ratio=0.7)
    assert validator.name == "Out-of-Sample Testing"

    result = validator.validate(dummy_strategy, rising_market_data)
    assert isinstance(result.passed, bool)
    assert "sharpe" in result.metrics
    assert "max_drawdown" in result.metrics


def test_out_of_sample_validator_empty(dummy_strategy: Strategy):
    """Test OutOfSampleValidator with empty data."""
    validator = OutOfSampleValidator()
    result = validator.validate(dummy_strategy, pd.DataFrame())
    assert result.passed is False


def test_statistical_significance_tester():
    """Test t-stat and p-value statistical significance computations."""
    # Constant positive returns (very strong t-stat/sharpe)
    returns = pd.Series([0.01] * 30)
    stats = StatisticalSignificanceTester.test_significance(returns)

    assert stats["t_stat"] > 0
    assert 0.0 <= stats["p_value"] <= 1.0
    assert stats["sharpe"] > 0
    assert stats["sortino"] > 0

    # Test few data points handling
    short_returns = pd.Series([0.01, 0.02])
    stats_short = StatisticalSignificanceTester.test_significance(short_returns)
    assert stats_short["t_stat"] == 0.0
    assert stats_short["p_value"] == 1.0


def test_robustness_tester(dummy_strategy: Strategy, rising_market_data: pd.DataFrame):
    """Test robustness noise injection and Sharpe perturbation."""
    # Ensure it returns a float representing the noisy Sharpe ratio
    sharpe_noisy = RobustnessTester.test_noise_perturbation(
        dummy_strategy, rising_market_data, noise_std=0.02
    )
    assert isinstance(sharpe_noisy, float)

    # Empty data should return 0.0
    assert RobustnessTester.test_noise_perturbation(dummy_strategy, pd.DataFrame()) == 0.0
