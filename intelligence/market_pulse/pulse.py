"""Market Pulse Generator for calculating market health indicators."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from intelligence.models import MarketPulse


class MarketPulseGenerator:
    """Generates market pulse indicators evaluating health, trend, volatility, and sentiment."""

    def calculate_trend(self, prices: list[float]) -> float:
        """Calculate normalized price trend from -1.0 (strongly bearish) to 1.0 (strongly bullish).

        Uses tanh mapping of the percentage return.
        """
        if len(prices) < 2:
            return 0.0
        pct_return = (prices[-1] - prices[0]) / prices[0]
        # Map to [-1, 1] using tanh with a scaling factor (e.g. 20.0 for 5% return to saturate)
        return math.tanh(pct_return * 20.0)

    def calculate_momentum(self, prices: list[float]) -> float:
        """Calculate normalized momentum from -1.0 to 1.0.

        Looks at the return of the second half of the series compared to the first half.
        """
        n = len(prices)
        if n < 4:
            return 0.0
        mid = n // 2
        first_half_close = prices[mid]
        second_half_return = (prices[-1] - first_half_close) / first_half_close
        return math.tanh(second_half_return * 40.0)

    def calculate_volatility(self, prices: list[float]) -> float:
        """Calculate normalized volatility.

        Computes the standard deviation of percentage returns.
        """
        if len(prices) < 3:
            return 0.0
        returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        stdev = math.sqrt(variance)
        # Annualize assuming 1-minute bars (approx 525,600 minutes per year)
        # Or just keep it as a raw normalized volatility score. Let's return raw stdev scaled by a factor.
        return stdev * 100.0

    def calculate_liquidity(
        self,
        bids: list[tuple[float, float]] | None,
        asks: list[tuple[float, float]] | None,
        avg_volume: float = 1.0,
    ) -> float:
        """Calculate normalized liquidity score based on order book depth or trading volume."""
        if not bids or not asks:
            # Fallback to volume-based proxy
            return min(5.0, max(0.0, avg_volume / 10.0))

        # Sum depth of top 5 levels
        bid_depth = sum(qty for _, qty in bids[:5])
        ask_depth = sum(qty for _, qty in asks[:5])
        total_depth = bid_depth + ask_depth
        # Normalize relative to a baseline of 10.0 units
        return total_depth / 10.0

    def calculate_participation(self, volumes: list[float]) -> float:
        """Calculate participation ratio (current volume vs historical average volume)."""
        if not volumes:
            return 1.0
        avg_vol = sum(volumes) / len(volumes)
        if avg_vol == 0.0:
            return 0.0
        return volumes[-1] / avg_vol

    def generate_pulse(
        self,
        prices: list[float],
        volumes: list[float],
        bids: list[tuple[float, float]] | None = None,
        asks: list[tuple[float, float]] | None = None,
        fear_index: float = 50.0,
        confidence: float = 1.0,
    ) -> MarketPulse:
        """Synthesize overall market health metrics into a MarketPulse snapshot.

        Args:
            prices: Historical price series.
            volumes: Historical volume series.
            bids: Bids list of [price, depth_amount].
            asks: Asks list of [price, depth_amount].
            fear_index: Market sentiment index (0 to 100).
            confidence: User/model input confidence score (0.0 to 1.0).

        Returns:
            MarketPulse object.
        """
        trend = self.calculate_trend(prices)
        momentum = self.calculate_momentum(prices)
        volatility = self.calculate_volatility(prices)
        avg_vol = sum(volumes) / len(volumes) if volumes else 1.0
        liquidity = self.calculate_liquidity(bids, asks, avg_volume=avg_vol)
        participation = self.calculate_participation(volumes)

        # Volatility index helper (clamped to 0.0 - 1.0)
        vol_score = min(1.0, volatility / 10.0)

        # Risk score calculation
        # Risk is higher when volatility is high, trend is negative, and fear is high
        bearishness = (1.0 - trend) / 2.0
        fear_factor = fear_index / 100.0
        risk = 0.4 * bearishness + 0.4 * vol_score + 0.2 * fear_factor
        risk = min(1.0, max(0.0, risk))

        # Overall score calculations
        # Healthier markets have upward trend, moderate volatility, high liquidity, low risk
        bullishness = (trend + 1.0) / 2.0
        momentum_score = (momentum + 1.0) / 2.0
        stability_score = 1.0 - risk

        overall_score = (
            0.3 * bullishness
            + 0.2 * momentum_score
            + 0.3 * stability_score
            + 0.2 * confidence
        )
        overall_score = min(1.0, max(0.0, overall_score))

        return MarketPulse(
            trend=trend,
            momentum=momentum,
            liquidity=liquidity,
            risk=risk,
            volatility=volatility,
            participation=participation,
            fear=fear_index,
            confidence=confidence,
            overall_score=overall_score,
            timestamp=datetime.now(timezone.utc),
        )
