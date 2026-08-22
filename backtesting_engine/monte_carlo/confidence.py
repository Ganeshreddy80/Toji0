"""Confidence Interval Engine for Monte Carlo simulation outputs (Sprint 8C)."""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

from backtesting_engine.monte_carlo.models.monte_carlo import ConfidenceInterval, SimulationResult


class MonteCarloConfidenceEngine:
    """Computes empirical percentile confidence intervals for key performance metrics."""

    METRICS = [
        ("Return", "total_return"),
        ("Drawdown", "max_drawdown"),
        ("Sharpe", "sharpe"),
        ("CAGR", "cagr"),
        ("Risk of Ruin", "ruin"),
    ]

    def compute_confidence_intervals(
        self,
        simulations: List[SimulationResult],
        confidence_levels: Sequence[float] = (0.90, 0.95, 0.99),
    ) -> List[ConfidenceInterval]:
        """Compute empirical percentile confidence intervals.

        Args:
            simulations: List of SimulationResult objects.
            confidence_levels: Target confidence levels (e.g. 0.90, 0.95, 0.99).

        Returns:
            List of ConfidenceInterval objects.
        """
        if not simulations:
            return self._empty_intervals(confidence_levels)

        intervals: List[ConfidenceInterval] = []

        # Extract metric arrays
        data_by_metric = {
            "total_return": np.array([s.total_return for s in simulations], dtype=np.float64),
            "max_drawdown": np.array([s.max_drawdown for s in simulations], dtype=np.float64),
            "sharpe": np.array([s.sharpe for s in simulations], dtype=np.float64),
            "cagr": np.array([s.cagr for s in simulations], dtype=np.float64),
            "ruin": np.array([1.0 if s.ruin else 0.0 for s in simulations], dtype=np.float64),
        }

        for display_name, field_name in self.METRICS:
            arr = data_by_metric[field_name]

            for level in sorted(confidence_levels):
                alpha = 1.0 - level
                lower_pct = (alpha / 2.0) * 100.0
                upper_pct = (1.0 - alpha / 2.0) * 100.0

                lower_bnd = float(np.percentile(arr, lower_pct))
                upper_bnd = float(np.percentile(arr, upper_pct))

                intervals.append(
                    ConfidenceInterval(
                        metric=display_name,
                        confidence_level=level,
                        lower_bound=lower_bnd,
                        upper_bound=upper_bnd,
                    )
                )

        return intervals

    def _empty_intervals(self, confidence_levels: Sequence[float]) -> List[ConfidenceInterval]:
        """Return zeroed intervals when no simulations exist."""
        intervals = []
        for display_name, _ in self.METRICS:
            for level in sorted(confidence_levels):
                intervals.append(
                    ConfidenceInterval(
                        metric=display_name,
                        confidence_level=level,
                        lower_bound=0.0,
                        upper_bound=0.0,
                    )
                )
        return intervals
