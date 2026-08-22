"""Signal engine converting factor values to signals.
"""

from __future__ import annotations

from typing import List
from research_platform.alpha_factory.interfaces import ISignalEngine
from research_platform.alpha_factory.models import AlphaSignal


class SignalEngine(ISignalEngine):
    """Generates signals based on factor values parameters."""

    def generate_signal(self, signal_id: str, factor_id: str, values: List[float]) -> AlphaSignal:
        if not values:
            direction = "FLAT"
            strength = 0.0
        else:
            mean = sum(values) / len(values)
            if mean > 0.5:
                direction = "BUY"
                strength = min(1.0, mean)
            elif mean < -0.5:
                direction = "SELL"
                strength = min(1.0, abs(mean))
            else:
                direction = "FLAT"
                strength = 0.0

        return AlphaSignal(
            signal_id=signal_id,
            factor_id=factor_id,
            direction=direction,
            strength=strength
        )
