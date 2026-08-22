"""Alpha engine combining multiple signals.
"""

from __future__ import annotations

from typing import List
from research_platform.alpha_factory.interfaces import IAlphaEngine
from research_platform.alpha_factory.models import AlphaCombo, AlphaSignal


class AlphaEngine(IAlphaEngine):
    """Combines buying/selling signals."""

    def combine_signals(self, combo_id: str, signals: List[AlphaSignal], weights: List[float]) -> AlphaCombo:
        return AlphaCombo(
            combo_id=combo_id,
            signals=signals,
            weights=weights
        )
