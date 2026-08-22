"""Robustness, sensitivity analysis, and neighborhood stability checker.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List

from research_platform.optimization_engine.models import (
    OptimizationTrial,
    RobustnessMetrics
)


class RobustnessAnalyzer:
    """Evaluates stability gradients and performance neighborhood variance."""

    @staticmethod
    def evaluate_parameter(
        param_name: str,
        trials: List[OptimizationTrial]
    ) -> RobustnessMetrics:
        """Compute stability indicators and variance across surrounding neighbors."""
        scores = []
        param_values = []

        for trial in trials:
            if not trial.is_valid:
                continue
            val = trial.parameters.values.get(param_name)
            if isinstance(val, (int, float)):
                param_values.append(float(val))
                scores.append(trial.score.composite_score)

        if len(scores) < 3:
            return RobustnessMetrics(
                sensitivity_gradient=0.0,
                parameter_stability_score=1.0,
                neighborhood_standard_deviation=0.0
            )

        # 1. Neighborhood standard deviation
        scores_arr = np.array(scores)
        std_dev = float(np.std(scores_arr))

        # 2. Gradient change (rough estimate of sensitivity)
        sorted_indices = np.argsort(param_values)
        sorted_params = np.array(param_values)[sorted_indices]
        sorted_scores = np.array(scores)[sorted_indices]

        # Calculate average absolute difference in scores divided by parameter step size
        gradients = []
        for i in range(len(sorted_params) - 1):
            step = sorted_params[i + 1] - sorted_params[i]
            if step > 0:
                grad = abs(sorted_scores[i + 1] - sorted_scores[i]) / step
                gradients.append(grad)

        avg_gradient = float(np.mean(gradients)) if gradients else 0.0

        # 3. Stability rank (high stability means low variance and low gradient)
        # Scale score from 0.0 (unstable) to 1.0 (highly robust)
        stability = float(1.0 / (1.0 + std_dev + avg_gradient))

        return RobustnessMetrics(
            sensitivity_gradient=avg_gradient,
            parameter_stability_score=stability,
            neighborhood_standard_deviation=std_dev
        )
