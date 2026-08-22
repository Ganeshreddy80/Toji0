"""Market scoring engine."""

from __future__ import annotations
from typing import Any
from toji_platform.market_universe.models import MarketStats, ScoredMarket

class MarketScorer:
    """Scores candidate markets using weighted normalizations of liquidity, volume, volatility, spread, and momentum."""

    def __init__(self, config: dict[str, Any]) -> None:
        weights = config.get("weights", {
            "liquidity": 0.3,
            "volume": 0.3,
            "volatility": 0.1,
            "spread": 0.1,
            "momentum": 0.2
        })
        # Normalize weights so they sum up to 1.0
        total = sum(weights.values())
        if total == 0.0:
            total = 1.0
        self.weights = {k: v / total for k, v in weights.items()}

    def score_market(self, stats: MarketStats, max_stats: dict[str, float]) -> ScoredMarket:
        """Computes weighted factor score dynamically relative to max values in the current cohort."""
        # Calculate raw normalized factors [0.0, 1.0]
        norm_liq = stats.liquidity_usd / max_stats.get("liquidity", 1.0)
        norm_vol = stats.volume_24h / max_stats.get("volume", 1.0)
        norm_vola = stats.volatility_24h / max_stats.get("volatility", 1.0)
        norm_mom = abs(stats.momentum_24h) / max_stats.get("momentum", 1.0)
        
        # Spread is normalized such that a lower spread yields a higher score [0.0, 1.0]
        norm_spread = stats.spread / max_stats.get("spread", 1.0)
        norm_spread_score = max(0.0, 1.0 - norm_spread)

        factors = {
            "liquidity": min(1.0, max(0.0, norm_liq)),
            "volume": min(1.0, max(0.0, norm_vol)),
            "volatility": min(1.0, max(0.0, norm_vola)),
            "spread": min(1.0, max(0.0, norm_spread_score)),
            "momentum": min(1.0, max(0.0, norm_mom))
        }

        # Weighted calculation
        score = sum(factors[k] * self.weights.get(k, 0.0) for k in factors)

        return ScoredMarket(
            symbol=stats.symbol,
            score=score,
            factors=factors,
            stats=stats
        )
