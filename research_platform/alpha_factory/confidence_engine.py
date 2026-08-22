"""Confidence engine computing signal confidence weights.
"""

from __future__ import annotations

from research_platform.alpha_factory.models import AlphaSignal


class ConfidenceEngine:
    """Evaluates signal confidence based on strength threshold levels."""

    def evaluate_confidence(self, signal: AlphaSignal) -> float:
        # Enforce basic confidence check
        if signal.direction == "FLAT":
            return 0.0
        return min(1.0, signal.strength * 1.2)
