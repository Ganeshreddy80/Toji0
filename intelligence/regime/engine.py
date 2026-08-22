"""Regime Engine for detecting structural market phases."""

from __future__ import annotations

import math
from typing import Literal

RegimePhase = Literal[
    "Accumulation",
    "Markup",
    "Distribution",
    "Markdown",
    "Expansion",
    "Compression",
    "Recovery",
    "Transition",
]


class RegimeEngine:
    """Classifies historical price and volume data into structural market regimes."""

    def __init__(
        self,
        compression_threshold: float = 0.005,
        expansion_threshold: float = 0.03,
        trend_threshold: float = 0.25,
    ) -> None:
        """Initialize the RegimeEngine.

        Args:
            compression_threshold: Volatility below this is classified as Compression.
            expansion_threshold: Volatility above this is classified as Expansion.
            trend_threshold: Absolute trend index above this indicates Markup/Markdown.
        """
        self.compression_threshold = compression_threshold
        self.expansion_threshold = expansion_threshold
        self.trend_threshold = trend_threshold

    def _calculate_metrics(
        self, prices: list[float], volumes: list[float]
    ) -> tuple[float, float, float, float, float]:
        """Helper to calculate inputs for regime detection."""
        n = len(prices)
        if n < 4:
            return 0.0, 0.0, 0.0, 1.0, 0.5

        # 1. Trend (normalized return mapped via tanh)
        pct_return = (prices[-1] - prices[0]) / prices[0]
        trend = math.tanh(pct_return * 20.0)

        # 2. Momentum (recent return vs older half return)
        mid = n // 2
        momentum = math.tanh(((prices[-1] - prices[mid]) / prices[mid]) * 40.0)

        # 3. Volatility (stdev of returns)
        returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, n)]
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        volatility = math.sqrt(variance)

        # 4. Volume Trend (last volume / avg volume)
        avg_vol = sum(volumes) / len(volumes) if volumes else 1.0
        volume_trend = (volumes[-1] / avg_vol) if avg_vol > 0 else 1.0

        # 5. Position in min-max range (0.0 to 1.0)
        p_min = min(prices)
        p_max = max(prices)
        range_span = p_max - p_min
        position = (prices[-1] - p_min) / range_span if range_span > 0 else 0.5

        return trend, momentum, volatility, volume_trend, position

    def detect_regime(self, prices: list[float], volumes: list[float]) -> RegimePhase:
        """Analyze price and volume trends to detect the current market phase.

        Phases classified:
        - Accumulation: Flat/ranging near bottom, average/high volume.
        - Markup: Strongly positive trend and momentum.
        - Distribution: Flat/ranging near top, high volume.
        - Markdown: Strongly negative trend and momentum.
        - Expansion: Extremely high volatility and rising volume.
        - Compression: Consolidating, extremely low volatility.
        - Recovery: Mildly positive trend and momentum following a downtrend.
        - Transition: Changing trend direction or conflicting indicators.

        Args:
            prices: Historical price series.
            volumes: Historical volume series.

        Returns:
            RegimePhase classification string.
        """
        if len(prices) < 4 or len(volumes) < 4:
            return "Transition"

        trend, momentum, volatility, volume_trend, position = self._calculate_metrics(
            prices, volumes
        )

        # 1. Volatility Compression Check
        if volatility < self.compression_threshold and abs(trend) < self.trend_threshold:
            return "Compression"

        # 2. Volatility Expansion Check
        if volatility > self.expansion_threshold and volume_trend > 1.2:
            return "Expansion"

        # 3. Strongly Trending Phases
        if trend > self.trend_threshold and momentum > 0.1:
            return "Markup"
        if trend < -self.trend_threshold and momentum < -0.1:
            return "Markdown"

        # 4. Ranging / Consolidating Phases (low absolute trend)
        # Position in min-max range helps distinguish accumulation (bottom) vs distribution (top)
        if abs(trend) <= self.trend_threshold:
            if position < 0.35:
                # Flat price near bottom, volume rising indicates institutional accumulation
                if volume_trend >= 1.0:
                    return "Accumulation"
                return "Recovery"
            elif position > 0.65:
                # Flat price near top, volume high/falling indicates distribution
                return "Distribution"
            else:
                # Middle of the range consolidation
                if momentum > 0.0:
                    return "Recovery"
                return "Transition"

        # 5. Fallback/Boundary cases
        if trend > 0.0 and momentum > 0.0:
            return "Recovery"

        return "Transition"
