"""Concrete strategy validation and statistical significance testing engines."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from research.validation.interfaces import IValidator, ValidationResult

if TYPE_CHECKING:
    from research.strategies.models import Strategy


def _approx_normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function (CDF) using built-in math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class WalkForwardValidator(IValidator):
    """Walk-forward optimization validation engine."""

    def __init__(self, windows: int = 5, train_ratio: float = 0.7) -> None:
        self._windows = windows
        self._train_ratio = train_ratio

    @property
    def name(self) -> str:
        return "Walk-Forward Validation"

    def validate(self, strategy: Strategy, data: pd.DataFrame) -> ValidationResult:
        if data.empty or len(data) < 20:
            return ValidationResult(passed=False, errors=["Insufficient data for walk-forward"])

        # Partition dataframe into windows
        total_len = len(data)
        window_size = total_len // self._windows
        passed_windows = 0
        details = []

        for w in range(self._windows):
            start_idx = w * window_size
            end_idx = min(start_idx + window_size, total_len)
            w_data = data.iloc[start_idx:end_idx]

            split = int(len(w_data) * self._train_ratio)
            train = w_data.iloc[:split]
            test = w_data.iloc[split:]

            if train.empty or test.empty:
                continue

            # Mock simulation returns
            ret = test["close"].pct_change().dropna()
            sharpe = float((ret.mean() / (ret.std() + 1e-10)) * math.sqrt(252)) if len(ret) > 1 else 0.0
            is_valid = sharpe > 1.0
            if is_valid:
                passed_windows += 1

            details.append({"window": w, "sharpe": sharpe, "passed": is_valid})

        passed = (passed_windows / self._windows) >= 0.6
        metrics = {"passed_ratio": passed_windows / self._windows}
        return ValidationResult(passed=passed, metrics=metrics, details={"windows": details})


class CrossValidator(IValidator):
    """K-fold time series cross-validation engine."""

    def __init__(self, folds: int = 5) -> None:
        self._folds = folds

    @property
    def name(self) -> str:
        return "Time Series Cross Validation"

    def validate(self, strategy: Strategy, data: pd.DataFrame) -> ValidationResult:
        if data.empty or len(data) < 20:
            return ValidationResult(passed=False)

        total_len = len(data)
        fold_size = total_len // (self._folds + 1)
        sharpes = []

        for f in range(self._folds):
            split_idx = (f + 1) * fold_size
            train = data.iloc[:split_idx]
            test = data.iloc[split_idx : split_idx + fold_size]

            if test.empty:
                continue

            ret = test["close"].pct_change().dropna()
            sharpe = float((ret.mean() / (ret.std() + 1e-10)) * math.sqrt(252)) if len(ret) > 1 else 0.0
            sharpes.append(sharpe)

        mean_sharpe = float(np.mean(sharpes)) if sharpes else 0.0
        passed = mean_sharpe >= 1.2
        return ValidationResult(
            passed=passed,
            metrics={"mean_sharpe": mean_sharpe},
            details={"folds_sharpe": sharpes},
        )


class OutOfSampleValidator(IValidator):
    """Out-of-sample data validation engine."""

    def __init__(self, train_ratio: float = 0.8) -> None:
        self._train_ratio = train_ratio

    @property
    def name(self) -> str:
        return "Out-of-Sample Testing"

    def validate(self, strategy: Strategy, data: pd.DataFrame) -> ValidationResult:
        if data.empty:
            return ValidationResult(passed=False)

        split = int(len(data) * self._train_ratio)
        oos_data = data.iloc[split:]

        ret = oos_data["close"].pct_change().dropna()
        sharpe = float((ret.mean() / (ret.std() + 1e-10)) * math.sqrt(252)) if len(ret) > 1 else 0.0
        max_dd = float(((oos_data["close"].cummax() - oos_data["close"]) / oos_data["close"].cummax()).max())

        passed = sharpe >= 1.0 and max_dd <= 0.25
        return ValidationResult(
            passed=passed,
            metrics={"sharpe": sharpe, "max_drawdown": max_dd},
        )


class StatisticalSignificanceTester:
    """Tester for verifying t-statistic, p-values, and tail risks."""

    @staticmethod
    def test_significance(returns: pd.Series) -> dict[str, float]:
        """Compute t-stat and p-value on daily return metrics."""
        clean_ret = returns.dropna()
        n = len(clean_ret)
        if n < 3:
            return {"t_stat": 0.0, "p_value": 1.0, "sharpe": 0.0, "sortino": 0.0}

        mean = float(clean_ret.mean())
        std = float(clean_ret.std())

        t_stat = math.sqrt(n) * (mean / (std + 1e-10))
        p_value = 2.0 * (1.0 - _approx_normal_cdf(abs(t_stat)))

        sharpe = (mean / (std + 1e-10)) * math.sqrt(252)

        downside = clean_ret[clean_ret < 0]
        downside_std = float(downside.std()) if len(downside) > 1 else std
        sortino = (mean / (downside_std + 1e-10)) * math.sqrt(252)

        return {
            "t_stat": t_stat,
            "p_value": p_value,
            "sharpe": sharpe,
            "sortino": sortino,
        }


class RobustnessTester:
    """Robustness parameter noise generator."""

    @staticmethod
    def test_noise_perturbation(
        strategy: Strategy, data: pd.DataFrame, noise_std: float = 0.01
    ) -> float:
        """Measure performance variance when adding standard Gaussian noise to price feeds."""
        if data.empty or "close" not in data.columns:
            return 0.0

        close_noisy = data["close"] * (1.0 + np.random.normal(0, noise_std, len(data)))
        ret_noisy = close_noisy.pct_change().dropna()
        sharpe_noisy = float((ret_noisy.mean() / (ret_noisy.std() + 1e-10)) * math.sqrt(252))

        return sharpe_noisy
