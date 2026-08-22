"""Hypothesis engine verifying statistical parameters.
"""

from __future__ import annotations

from research_platform.research_lab.interfaces import IHypothesisEngine
from research_platform.research_lab.models import Hypothesis


class HypothesisEngine(IHypothesisEngine):
    """Verifies significance levels p-values checks."""

    def verify_hypothesis(self, hypothesis_id: str, description: str, p_value: float) -> Hypothesis:
        # Signifance level alpha = 0.05
        verified = p_value < 0.05
        return Hypothesis(
            hypothesis_id=hypothesis_id,
            description=description,
            p_value=p_value,
            verified=verified
        )
