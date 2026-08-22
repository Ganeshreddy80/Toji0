"""Market ranking engine."""

from __future__ import annotations
from typing import Any
from toji_platform.market_universe.models import ScoredMarket, RankedMarket

class MarketRanker:
    """Sorts markets deterministically and categorizes them into quality Tiers A, B, C, and D."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def rank_markets(self, scored_markets: list[ScoredMarket]) -> list[RankedMarket]:
        # Deterministic sorting: primary key is score descending, secondary key is alphabetical symbol ascending
        sorted_scored = sorted(scored_markets, key=lambda x: (-x.score, x.symbol))

        total_count = len(sorted_scored)
        ranked = []

        for i, sm in enumerate(sorted_scored):
            rank = i + 1
            if total_count == 0:
                tier = "D"
            else:
                pct = rank / total_count
                # Quality Tier categorization
                if pct <= 0.15:
                    tier = "A"
                elif pct <= 0.40:
                    tier = "B"
                elif pct <= 0.80:
                    tier = "C"
                else:
                    tier = "D"

            ranked.append(RankedMarket(
                symbol=sm.symbol,
                rank=rank,
                score=sm.score,
                tier=tier,
                stats=sm.stats
            ))

        return ranked
