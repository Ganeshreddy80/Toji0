"""Alpha Decay tracking and retirement scoring.
"""

from __future__ import annotations

import math
import numpy as np
from typing import List

from research_platform.alpha_factory.models import AlphaDecayReport


class AlphaDecayEngine:
    """Monitors decay rates, information half-life curves, and calculates retirement score flags."""

    @classmethod
    def calculate_decay(cls, candidate_id: str, rolling_ics: List[float]) -> AlphaDecayReport:
        """Compute half-life of information decay and generate decay report."""
        if not rolling_ics or len(rolling_ics) < 2:
            return AlphaDecayReport(
                candidate_id=candidate_id,
                half_life_days=0.0,
                rolling_ic=rolling_ics,
                decay_curve=[],
                retirement_score=1.0  # retired
            )

        # Standard decay curve: values normalized compared to the initial IC
        initial_ic = abs(rolling_ics[0]) + 1e-10
        decay_curve = [abs(ic) / initial_ic for ic in rolling_ics]

        # Fit simple exponential decay: IC_t = IC_0 * e^(-lambda * t)
        # ln(IC_t / IC_0) = -lambda * t
        t_values = np.arange(len(decay_curve))
        log_ratios = np.log(np.clip(decay_curve, 1e-5, 1.0))
        
        # Fit slope using linear regression (y = m * x)
        # m = sum(x * y) / sum(x^2)
        numerator = np.sum(t_values * log_ratios)
        denominator = np.sum(t_values ** 2) + 1e-10
        neg_lambda = numerator / denominator
        
        decay_rate = max(-neg_lambda, 1e-10)
        # half-life = ln(2) / decay_rate
        half_life_days = math.log(2.0) / decay_rate

        # Retirement score: 0.0 (fresh/valuable) to 1.0 (dead/retired)
        # If half-life is short, or current rolling IC is very low
        current_ic = abs(rolling_ics[-1])
        if current_ic < 0.01:
            retirement_score = 1.0
        elif half_life_days < 5.0:
            retirement_score = 0.9
        else:
            # Scale retirement score based on current IC compared to a target threshold of 0.05
            retirement_score = max(1.0 - (current_ic / 0.05), 0.0)

        return AlphaDecayReport(
            candidate_id=candidate_id,
            half_life_days=float(half_life_days),
            rolling_ic=rolling_ics,
            decay_curve=decay_curve,
            retirement_score=float(retirement_score)
        )
