"""Market Universe Engine pipeline coordinator."""

from __future__ import annotations
from typing import Any

from toji_platform.market_universe.models import MarketStats, RankedMarket
from toji_platform.market_universe.filters import MarketFilter
from toji_platform.market_universe.scorer import MarketScorer
from toji_platform.market_universe.ranking import MarketRanker

class MarketUniverseEngine:
    """Coordinating engine for filtering, scoring, and ranking candidate trading markets."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.filter = MarketFilter(config.get("filters", {}))
        self.scorer = MarketScorer(config.get("scoring", {}))
        self.ranker = MarketRanker(config.get("ranking", {}))

    def evaluate_universe(self, raw_markets: list[MarketStats]) -> list[RankedMarket]:
        """Runs the whole pipeline synchronously: Filters out candidates -> calculates cohort stats -> scores -> ranks."""
        # 1. Filter
        filtered = [m for m in raw_markets if self.filter.evaluate(m)]
        if not filtered:
            return []

        # 2. Extract maximum cohort statistical metrics to use as dynamic relative dividers in scoring normalizations
        max_stats = {
            "liquidity": max((m.liquidity_usd for m in filtered), default=1.0),
            "volume": max((m.volume_24h for m in filtered), default=1.0),
            "volatility": max((m.volatility_24h for m in filtered), default=1.0),
            "spread": max((m.spread for m in filtered), default=1.0),
            "momentum": max((abs(m.momentum_24h) for m in filtered), default=1.0),
        }
        # Prevent dividing by zero
        for k in max_stats:
            if max_stats[k] == 0.0:
                max_stats[k] = 1.0

        # 3. Score
        scored = [self.scorer.score_market(m, max_stats) for m in filtered]

        # 4. Rank
        ranked = self.ranker.rank_markets(scored)
        return ranked
