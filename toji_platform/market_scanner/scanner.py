"""Market Scanner coordinator."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from data.schemas.market_data import OHLCV
from toji_platform.market_universe.models import RankedMarket
from toji_platform.market_scanner.models import MarketMetrics, MarketScan
from toji_platform.market_scanner.analyzer import MarketAnalyzer
from toji_platform.market_scanner import indicators

class MarketScanner:
    """Continuous scanner mapping RankedMarket candidates to condition analysis snapshots."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.analyzer = MarketAnalyzer(config)

    def scan_market(
        self,
        ranked_market: RankedMarket,
        candles: list[OHLCV],
        last_update_time: datetime
    ) -> MarketScan:
        """Processes historical/real-time candles and ranked market metrics to build a MarketScan."""
        # 1. Safe extraction of close prices
        prices = [c.close for c in candles]

        # 2. Calculate Indicators
        atr = indicators.calculate_atr(candles, period=self.config.get("atr_period", 14))
        volatility = ranked_market.stats.volatility_24h
        rsi = indicators.calculate_rsi(prices, period=self.config.get("rsi_period", 14))
        
        # Calculate relative volume
        if len(candles) > 1:
            avg_vol = sum(c.volume for c in candles[:-1]) / (len(candles) - 1)
            current_vol = candles[-1].volume
            relative_volume = current_vol / avg_vol if avg_vol > 0.0 else 1.0
        else:
            relative_volume = 1.0

        now = datetime.now(timezone.utc)
        if last_update_time.tzinfo is None:
            last_update_time = last_update_time.replace(tzinfo=timezone.utc)
        
        time_since_sec = (now - last_update_time).total_seconds()

        # 3. Populate metrics
        metrics = MarketMetrics(
            atr=atr,
            volatility=volatility,
            rsi=rsi,
            relative_volume=relative_volume,
            spread=ranked_market.stats.spread,
            liquidity_depth=ranked_market.stats.liquidity_usd,
            time_since_last_update_sec=max(0.0, time_since_sec)
        )

        # 4. Analyze conditions and scores
        states, confidence, quality, diagnostics = self.analyzer.analyze(ranked_market.symbol, metrics)

        return MarketScan(
            symbol=ranked_market.symbol,
            timestamp=now,
            market_states=states,
            metrics=metrics,
            confidence_score=confidence,
            quality_score=quality,
            diagnostics=diagnostics
        )
