"""Robustness engine scoring parameter sensitivities.
"""

from __future__ import annotations

from typing import List
from research_platform.walk_forward.interfaces import IRobustnessEngine
from research_platform.walk_forward.models import SensitivityScore


class RobustnessEngine(IRobustnessEngine):
    """Calculates sensitivity scores from parameter variations and outcomes."""

    def analyze_sensitivity(self, parameter_name: str, values: List[float], outcomes: List[float]) -> SensitivityScore:
        if not outcomes:
            dev = 0.0
        else:
            mean = sum(outcomes) / len(outcomes)
            variance = sum((val - mean) ** 2 for val in outcomes) / len(outcomes)
            dev = variance ** 0.5

        # Robustness score calculation (lower variation indicates higher robustness)
        score = 1.0 / (1.0 + dev)

        return SensitivityScore(
            parameter_name=parameter_name,
            values=values,
            metrics_deviation=dev,
            score=score
        )
