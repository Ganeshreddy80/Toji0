"""Ranking engine ranking buying/selling signals based on strength metrics.
"""

from __future__ import annotations

from typing import List
from research_platform.alpha_factory.models import AlphaSignal


class RankingEngine:
    """Ranks signals based on strength scores."""

    def rank_signals(self, signals: List[AlphaSignal]) -> List[AlphaSignal]:
        # Sort descending by strength
        sorted_signals = list(signals)
        sorted_signals.sort(key=lambda s: s.strength, reverse=True)
        return sorted_signals
