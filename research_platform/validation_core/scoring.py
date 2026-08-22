"""Research Score aggregator engine.
"""

from __future__ import annotations

from typing import Dict

from research_platform.validation_core.models import ResearchScore


class ResearchScoreCalculator:
    """Combines metrics from validation checks into a single score (0-100 scale)."""

    @staticmethod
    def calculate(
        quality: float,
        freshness: float,
        drift_psi: float,
        pbo: float,
        psr: float,
        dsr: float,
        spa_p_value: float,
        regime_stability: float,
        weights: Dict[str, float] = None
    ) -> ResearchScore:
        """Compute the composite ResearchScore."""
        default_weights = {
            "quality": 0.15,
            "freshness": 0.10,
            "drift": 0.15,
            "pbo": 0.15,
            "psr": 0.15,
            "dsr": 0.15,
            "spa": 0.15
        }
        if weights:
            # Override defaults with provided weights
            for k, v in weights.items():
                if k in default_weights:
                    default_weights[k] = v

        # Normalize weights sum
        w_sum = sum(default_weights.values())
        if w_sum > 0:
            for k in default_weights:
                default_weights[k] /= w_sum

        # Calculate contributions (each contribution scale: 0 to 100)
        # Drift score: lower PSI is better, e.g. PSI=0 is 100, PSI>=0.5 is 0
        drift_score = max(100.0 - (drift_psi * 200.0), 0.0)

        # PBO score: lower overfitting probability is better
        pbo_score = (1.0 - pbo) * 100.0

        # PSR/DSR scores: probability scale 0.0 to 1.0 maps directly to 100
        psr_score = psr * 100.0
        dsr_score = dsr * 100.0

        # SPA score: low p-value rejects null (meaning strategy is superior)
        spa_score = (1.0 - spa_p_value) * 100.0

        quality_val = quality * 100.0
        freshness_val = freshness * 100.0

        # Calculate weighted average
        quality_contrib = default_weights["quality"] * quality_val
        freshness_contrib = default_weights["freshness"] * freshness_val
        drift_contrib = default_weights["drift"] * drift_score
        pbo_contrib = default_weights["pbo"] * pbo_score
        psr_contrib = default_weights["psr"] * psr_score
        dsr_contrib = default_weights["dsr"] * dsr_score
        spa_contrib = default_weights["spa"] * spa_score

        # regime stability estimation placeholder contribution (10% of total if not defined, or mapped)
        regime_contrib = 0.0

        score_value = (
            quality_contrib +
            freshness_contrib +
            drift_contrib +
            pbo_contrib +
            psr_contrib +
            dsr_contrib +
            spa_contrib
        )

        return ResearchScore(
            score_value=float(np.clip(score_value, 0.0, 100.0)),
            quality_contrib=float(quality_contrib),
            freshness_contrib=float(freshness_contrib),
            drift_contrib=float(drift_contrib),
            pbo_contrib=float(pbo_contrib),
            psr_contrib=float(psr_contrib),
            dsr_contrib=float(dsr_contrib),
            spa_contrib=float(spa_contrib),
            regime_stability_contrib=float(regime_contrib)
        )
import numpy as np
