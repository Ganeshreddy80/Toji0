"""Statistics Engine for Monte Carlo simulation distributions (Sprint 8C)."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from backtesting_engine.monte_carlo.models.monte_carlo import SimulationResult


class MonteCarloStatisticsEngine:
    """Computes statistical distribution metrics across simulation runs."""

    PERCENTILE_LEVELS = [1.0, 5.0, 10.0, 25.0, 50.0, 75.0, 90.0, 95.0, 99.0]

    def compute_statistics(self, simulations: List[SimulationResult]) -> Dict[str, Any]:
        """Compute comprehensive statistical metrics from simulation results.

        Args:
            simulations: List of SimulationResult instances.

        Returns:
            Dictionary containing statistical metrics, summary, and percentile table.
        """
        if not simulations:
            return self._empty_statistics()

        ending_equity = np.array([s.ending_equity for s in simulations], dtype=np.float64)
        max_drawdown = np.array([s.max_drawdown for s in simulations], dtype=np.float64)
        total_return = np.array([s.total_return for s in simulations], dtype=np.float64)
        cagr = np.array([s.cagr for s in simulations], dtype=np.float64)
        sharpe = np.array([s.sharpe for s in simulations], dtype=np.float64)

        expected_return = float(np.mean(total_return))
        expected_drawdown = float(np.mean(max_drawdown))

        # Metrics map for batch computation
        metrics_data = {
            "ending_equity": ending_equity,
            "max_drawdown": max_drawdown,
            "total_return": total_return,
            "cagr": cagr,
            "sharpe": sharpe,
        }

        stats_by_metric = {}
        for key, arr in metrics_data.items():
            stats_by_metric[key] = self.compute_array_stats(arr)

        percentile_table = self._build_percentile_table(metrics_data)

        summary = {
            "expected_return": expected_return,
            "expected_drawdown": expected_drawdown,
            "median_return": stats_by_metric["total_return"]["median"],
            "median_drawdown": stats_by_metric["max_drawdown"]["median"],
            "return_std": stats_by_metric["total_return"]["std"],
            "drawdown_std": stats_by_metric["max_drawdown"]["std"],
            "return_skewness": stats_by_metric["total_return"]["skewness"],
            "return_kurtosis": stats_by_metric["total_return"]["kurtosis"],
            "sharpe_mean": stats_by_metric["sharpe"]["mean"],
            "sharpe_median": stats_by_metric["sharpe"]["median"],
            "metrics": stats_by_metric,
        }

        return {
            "expected_return": expected_return,
            "expected_drawdown": expected_drawdown,
            "percentile_table": percentile_table,
            "summary": summary,
        }

    @staticmethod
    def compute_array_stats(arr: np.ndarray) -> Dict[str, float]:
        """Compute mean, median, variance, std, skewness, kurtosis for a 1D float array.

        Mathematical Formulas Used:
            - Mean: mu = sum(x_i) / N
            - Median: 50th percentile value
            - Variance (sample): s^2 = sum((x_i - mu)^2) / (N - 1) for N > 1
            - Standard Deviation (sample): s = sqrt(s^2)
            - Skewness (population central moment ratio):
                m_2 = sum((x_i - mu)^2) / N
                m_3 = sum((x_i - mu)^3) / N
                skewness = m_3 / (m_2^(3/2))
            - Kurtosis (population excess kurtosis):
                m_4 = sum((x_i - mu)^4) / N
                kurtosis = (m_4 / (m_2^2)) - 3.0
        """
        n = len(arr)
        if n == 0:
            return {
                "mean": 0.0,
                "median": 0.0,
                "variance": 0.0,
                "std": 0.0,
                "skewness": 0.0,
                "kurtosis": 0.0,
            }

        mean_val = float(np.mean(arr))
        median_val = float(np.median(arr))
        var_val = float(np.var(arr, ddof=1)) if n > 1 else 0.0
        std_val = float(np.std(arr, ddof=1)) if n > 1 else 0.0

        # Mathematically consistent central moment calculations
        diffs = arr - mean_val
        m2 = float(np.mean(diffs**2))  # Second central moment (population variance)
        m3 = float(np.mean(diffs**3))  # Third central moment
        m4 = float(np.mean(diffs**4))  # Fourth central moment

        if m2 > 1e-12 and n > 2:
            skew_val = m3 / (m2**1.5)
            kurt_val = (m4 / (m2**2)) - 3.0  # Excess kurtosis
        else:
            skew_val = 0.0
            kurt_val = 0.0

        return {
            "mean": mean_val,
            "median": median_val,
            "variance": var_val,
            "std": std_val,
            "skewness": skew_val,
            "kurtosis": kurt_val,
        }

    def _build_percentile_table(self, metrics_data: Dict[str, np.ndarray]) -> Dict[str, Dict[str, float]]:
        """Build structured percentile table mapping percentile labels to metric values."""
        table: Dict[str, Dict[str, float]] = {}

        for pct in self.PERCENTILE_LEVELS:
            pct_label = f"{pct:g}%"
            table[pct_label] = {}
            for metric_name, arr in metrics_data.items():
                val = float(np.percentile(arr, pct)) if len(arr) > 0 else 0.0
                table[pct_label][metric_name] = val

        return table

    def _empty_statistics(self) -> Dict[str, Any]:
        """Return default statistical structure when no simulations exist."""
        return {
            "expected_return": 0.0,
            "expected_drawdown": 0.0,
            "percentile_table": {},
            "summary": {
                "expected_return": 0.0,
                "expected_drawdown": 0.0,
                "median_return": 0.0,
                "median_drawdown": 0.0,
                "return_std": 0.0,
                "drawdown_std": 0.0,
                "return_skewness": 0.0,
                "return_kurtosis": 0.0,
                "sharpe_mean": 0.0,
                "sharpe_median": 0.0,
                "metrics": {},
            },
        }
