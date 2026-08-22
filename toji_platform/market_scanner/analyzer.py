"""Market condition analyzer."""

from __future__ import annotations
from typing import Any

from toji_platform.market_scanner.models import MarketMetrics
from toji_platform.market_scanner import state

class MarketAnalyzer:
    """Analyzes market metrics to determine active states, quality, and confidence scores."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def analyze(self, symbol: str, metrics: MarketMetrics) -> tuple[list[str], float, float, dict[str, Any]]:
        states = []
        diagnostics = {}

        # 1. Stale data check
        stale_threshold = self.config.get("stale_threshold_sec", 30.0)
        is_stale = metrics.time_since_last_update_sec > stale_threshold
        if is_stale:
            states.append(state.DATA_STALE)

        # 2. Volatility checks
        vol_threshold = self.config.get("volatility_threshold", 0.03)
        if metrics.volatility > vol_threshold:
            states.append(state.HIGH_VOLATILITY)

        # 3. Liquidity checks
        min_liq = self.config.get("min_liquidity_usd", 10000.0)
        if metrics.liquidity_depth < min_liq:
            states.append(state.LOW_LIQUIDITY)

        # 4. Volume checks
        rel_vol_threshold = self.config.get("unusual_volume_threshold", 2.0)
        if metrics.relative_volume > rel_vol_threshold:
            states.append(state.UNUSUAL_VOLUME)

        # 5. Trend / Momentum (RSI boundaries)
        if metrics.rsi >= 70.0:
            states.append(state.TRENDING_UP)
        elif metrics.rsi <= 30.0:
            states.append(state.TRENDING_DOWN)
        else:
            states.append(state.RANGING)

        # 6. Overall Health
        max_spread = self.config.get("max_spread", 0.01)
        is_unhealthy = is_stale or metrics.spread > max_spread or metrics.liquidity_depth < min_liq
        if is_unhealthy:
            states.append(state.UNHEALTHY)
        else:
            states.append(state.HEALTHY)

        # 7. Confidence Score (0.0 to 1.0)
        confidence = 1.0
        if is_stale:
            confidence -= 0.5
        if metrics.spread > max_spread:
            confidence -= 0.3
        confidence = max(0.0, confidence)

        # 8. Quality Score (0.0 to 1.0)
        quality = 1.0
        if metrics.volatility > vol_threshold:
            quality -= 0.2
        if metrics.liquidity_depth < min_liq:
            quality -= 0.3
        if metrics.spread > max_spread:
            quality -= 0.2
        if is_stale:
            quality -= 0.3
        quality = max(0.0, quality)

        diagnostics["max_spread_configured"] = max_spread
        diagnostics["volatility_threshold_configured"] = vol_threshold

        return states, confidence, quality, diagnostics
