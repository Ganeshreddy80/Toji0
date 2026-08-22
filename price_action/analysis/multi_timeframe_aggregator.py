"""Multi-timeframe price action aggregator."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Dict

from price_action.core.enums import MarketRegimeType, TrendDirection
from price_action.core.interfaces import IMultiTimeframeAggregator
from price_action.core.models import (
    MultiTimeframePriceActionSnapshot,
    TimeframePriceActionSnapshot,
)

logger = logging.getLogger(__name__)


class MultiTimeframeAggregator(IMultiTimeframeAggregator):
    """Aggregates single-timeframe price action snapshots into an MTF snapshot with confluence scoring."""

    def aggregate_snapshots(
        self, symbol: str, timeframe_snapshots: Dict[str, TimeframePriceActionSnapshot]
    ) -> MultiTimeframePriceActionSnapshot:
        """Combine single-timeframe analyses into an aggregated MTF snapshot."""
        if not timeframe_snapshots:
            return MultiTimeframePriceActionSnapshot(
                symbol=symbol,
                timeframe_snapshots={},
                primary_regime=MarketRegimeType.RANGING,
                primary_trend=TrendDirection.SIDEWAYS,
                confluence_score=0.0,
            )

        # Priority higher timeframes for primary macro regime and trend
        tf_order = ["1d", "4h", "1h", "15m", "5m", "1m"]
        primary_regime = MarketRegimeType.RANGING
        primary_trend = TrendDirection.SIDEWAYS

        for tf in tf_order:
            if tf in timeframe_snapshots:
                snap = timeframe_snapshots[tf]
                primary_regime = snap.regime.regime
                primary_trend = snap.trend.direction
                break

        # Calculate multi-timeframe trend alignment confluence score
        trends = [s.trend.direction for s in timeframe_snapshots.values()]
        bullish_cnt = sum(1 for t in trends if t == TrendDirection.BULLISH)
        bearish_cnt = sum(1 for t in trends if t == TrendDirection.BEARISH)
        total_tf = len(trends)

        confluence_score = 50.0
        if total_tf > 0:
            max_align = max(bullish_cnt, bearish_cnt)
            confluence_score = round((max_align / total_tf) * 100.0, 2)

        return MultiTimeframePriceActionSnapshot(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            timeframe_snapshots=timeframe_snapshots,
            primary_regime=primary_regime,
            primary_trend=primary_trend,
            confluence_score=confluence_score,
        )
