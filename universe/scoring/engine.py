"""Multi-factor weighted asset scoring engine.

Computes individual factor scores and a weighted composite
for each asset in the universe. All weights are configurable
via ScoringWeights in UniverseConfig.
"""

from __future__ import annotations

import logging
import math

from universe.core.interfaces import IAssetScorer
from universe.core.models import AssetScore, ScoringWeights, UniverseAsset

logger = logging.getLogger(__name__)


class ScoringEngine(IAssetScorer):
    """Compute multi-factor weighted scores for universe assets.

    Factor scores (0-100):
    - Liquidity: Based on 24h volume (log-scaled)
    - Volatility: Based on realized volatility (inverted — moderate = best)
    - Momentum: Based on 24h price change percentage
    - Correlation: Based on exchange coverage as proxy (more exchanges = more independent)
    - Exchange Coverage: Based on number of exchanges listing the asset

    All individual scores are normalized to [0, 100] using min-max
    scaling or log-scaling depending on the factor distribution.
    """

    def __init__(self, weights: ScoringWeights | None = None) -> None:
        self._weights = weights or ScoringWeights()

    def score(self, assets: list[UniverseAsset]) -> list[UniverseAsset]:
        """Score each asset and attach an AssetScore.

        Returns a new list with score fields populated.
        """
        if not assets:
            return []

        # Compute population statistics for normalization
        volumes = [a.volume_24h_usd for a in assets]
        volatilities = [a.volatility for a in assets]
        price_changes = [a.price_change_pct_24h for a in assets]
        exchange_counts = [float(len(a.exchanges)) for a in assets]

        vol_max = max(volumes) if volumes else 1.0
        vola_max = max(volatilities) if volatilities else 1.0
        pc_min = min(price_changes) if price_changes else 0.0
        pc_max = max(price_changes) if price_changes else 1.0
        ex_max = max(exchange_counts) if exchange_counts else 1.0

        scored: list[UniverseAsset] = []
        for asset in assets:
            liquidity = self._score_liquidity(asset.volume_24h_usd, vol_max)
            volatility = self._score_volatility(asset.volatility, vola_max)
            momentum = self._score_momentum(
                asset.price_change_pct_24h, pc_min, pc_max
            )
            correlation = self._score_correlation(
                len(asset.exchanges), ex_max
            )
            exchange_cov = self._score_exchange_coverage(
                len(asset.exchanges), ex_max
            )

            composite = self._compute_composite(
                liquidity, volatility, momentum, correlation, exchange_cov
            )

            asset_score = AssetScore(
                liquidity_score=round(liquidity, 2),
                volatility_score=round(volatility, 2),
                momentum_score=round(momentum, 2),
                correlation_score=round(correlation, 2),
                exchange_coverage_score=round(exchange_cov, 2),
                composite_score=round(composite, 2),
            )

            scored_asset = asset.model_copy(update={"score": asset_score})
            scored.append(scored_asset)

        logger.info("Scoring: Scored %d assets", len(scored))
        return scored

    def _score_liquidity(self, volume_usd: float, max_volume: float) -> float:
        """Log-scaled liquidity score.

        Log scaling prevents ultra-high-volume assets from dominating.
        """
        if volume_usd <= 0 or max_volume <= 0:
            return 0.0
        log_vol = math.log1p(volume_usd)
        log_max = math.log1p(max_volume)
        return min(100.0, (log_vol / log_max) * 100.0) if log_max > 0 else 0.0

    def _score_volatility(self, volatility: float, max_volatility: float) -> float:
        """Volatility score — moderate volatility is best.

        Uses an inverted bell curve: 0% and very high% vol both score low.
        Moderate volatility (around 30-60% of max) scores highest.
        """
        if max_volatility <= 0:
            return 50.0  # Neutral if no volatility data

        normalized = volatility / max_volatility
        # Bell curve peaking at 0.4 (40% of max)
        score = 100.0 * math.exp(-((normalized - 0.4) ** 2) / 0.18)
        return min(100.0, max(0.0, score))

    def _score_momentum(
        self, pct_change: float, min_change: float, max_change: float
    ) -> float:
        """Momentum score — positive momentum scores higher.

        Normalized to [0, 100] within the population's range.
        """
        spread = max_change - min_change
        if spread <= 0:
            return 50.0
        return min(100.0, max(0.0, ((pct_change - min_change) / spread) * 100.0))

    def _score_correlation(
        self, exchange_count: int, max_exchanges: float
    ) -> float:
        """Correlation proxy score.

        Assets on more exchanges tend to have more independent price discovery.
        Uses exchange count as a proxy for correlation diversification value.
        """
        if max_exchanges <= 0:
            return 50.0
        return min(100.0, (exchange_count / max_exchanges) * 100.0)

    def _score_exchange_coverage(
        self, exchange_count: int, max_exchanges: float
    ) -> float:
        """Exchange coverage score — more exchanges = higher score."""
        if max_exchanges <= 0:
            return 0.0
        return min(100.0, (exchange_count / max_exchanges) * 100.0)

    def _compute_composite(
        self,
        liquidity: float,
        volatility: float,
        momentum: float,
        correlation: float,
        exchange_cov: float,
    ) -> float:
        """Weighted average of all factor scores."""
        w = self._weights
        total_weight = w.total
        if total_weight <= 0:
            return 0.0

        weighted_sum = (
            w.liquidity * liquidity
            + w.volatility * volatility
            + w.momentum * momentum
            + w.correlation * correlation
            + w.exchange_coverage * exchange_cov
        )
        return min(100.0, weighted_sum / total_weight)
