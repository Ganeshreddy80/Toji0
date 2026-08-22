"""Asset Health Calculator for evaluating asset-specific metrics and risks."""

from __future__ import annotations

import math
from typing import Any


class AssetHealthCalculator:
    """Calculates quantitative asset health scores based on volume, spreads, volatility, and manipulation risk."""

    def __init__(
        self,
        volume_baseline: float = 10000.0,
        spread_baseline: float = 0.001,
        volatility_baseline: float = 0.02,
    ) -> None:
        """Initialize the AssetHealthCalculator.

        Args:
            volume_baseline: Normal/average expected volume to scale liquidity score.
            spread_baseline: Baseline bid-ask spread percentage.
            volatility_baseline: Expected baseline volatility.
        """
        self.volume_baseline = volume_baseline
        self.spread_baseline = spread_baseline
        self.volatility_baseline = volatility_baseline

    def calculate_volatility(self, prices: list[float]) -> float:
        """Calculate standard deviation of price returns."""
        if len(prices) < 3:
            return 0.0
        returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        return math.sqrt(variance)

    def calculate_manipulation_risk(
        self,
        avg_volume: float,
        avg_spread: float,
        volatility: float,
    ) -> float:
        """Calculate asset manipulation risk score from 0.0 (immune) to 1.0 (highly vulnerable).

        High risk is driven by low volume, wide spreads, and abnormal volatility.
        """
        # Low volume factor: 1.0 when volume is 0, decaying towards 0 as volume rises
        vol_factor = math.exp(-avg_volume / self.volume_baseline) if avg_volume > 0 else 1.0

        # Spread factor: maps spread to 0.0 - 1.0 (higher spread = higher risk)
        spread_factor = avg_spread / (avg_spread + self.spread_baseline) if avg_spread > 0 else 0.0

        # Volatility factor: maps volatility to 0.0 - 1.0
        vol_factor_scaled = volatility / (volatility + self.volatility_baseline) if volatility > 0 else 0.0

        # Weighted calculation
        risk = 0.45 * vol_factor + 0.35 * spread_factor + 0.20 * vol_factor_scaled
        return min(1.0, max(0.0, risk))

    def evaluate_health(
        self,
        prices: list[float],
        volumes: list[float],
        spreads: list[float],
        funding_rates: list[float] | None = None,
        open_interests: list[float] | None = None,
    ) -> dict[str, Any]:
        """Compute the combined Health Score and metrics dictionary for an asset.

        Args:
            prices: Price series.
            volumes: Volume series.
            spreads: Spreads list (represented as decimal percentages, e.g. 0.0005 for 5 bps).
            funding_rates: Optional funding rate series.
            open_interests: Optional open interest series.

        Returns:
            Dictionary containing metrics: liquidity, spread, volume, volatility,
            funding, open_interest, manipulation_risk, and health_score.
        """
        # 1. Base calculations
        avg_vol = sum(volumes) / len(volumes) if volumes else 0.0
        avg_spread = sum(spreads) / len(spreads) if spreads else 0.0005
        volatility = self.calculate_volatility(prices)

        latest_funding = funding_rates[-1] if funding_rates else 0.0
        latest_oi = open_interests[-1] if open_interests else 0.0

        # 2. Sub-metric scores
        # Liquidity proxy (0.0 to 1.0): scales with volume and inverse spread
        liquidity_score = (1.0 - math.exp(-avg_vol / self.volume_baseline)) * (
            self.spread_baseline / (avg_spread + 1e-6)
        )
        liquidity_score = min(1.0, max(0.0, liquidity_score))

        # Manipulation Risk
        manipulation_risk = self.calculate_manipulation_risk(avg_vol, avg_spread, volatility)

        # 3. Overall Health Score (0.0 - 1.0)
        # Healthy assets have good liquidity, low manipulation risk, low absolute funding, stable volatility
        liquidity_weight = 0.35
        risk_weight = 0.35
        vol_weight = 0.20
        funding_weight = 0.10

        vol_penalty = volatility / (volatility + self.volatility_baseline * 2) if volatility > 0 else 0.0
        vol_score = 1.0 - vol_penalty

        funding_penalty = min(1.0, abs(latest_funding) * 200.0)  # penalize high absolute funding rates
        funding_score = 1.0 - funding_penalty

        health_score = (
            liquidity_weight * liquidity_score
            + risk_weight * (1.0 - manipulation_risk)
            + vol_weight * vol_score
            + funding_weight * funding_score
        )
        health_score = min(1.0, max(0.0, health_score))

        return {
            "liquidity": liquidity_score,
            "spread": avg_spread,
            "volume": avg_vol,
            "volatility": volatility,
            "funding": latest_funding,
            "open_interest": latest_oi,
            "manipulation_risk": manipulation_risk,
            "health_score": health_score,
        }
