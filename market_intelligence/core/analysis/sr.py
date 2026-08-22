"""Support and Resistance Horizontal Levels Clustering Engine."""

from __future__ import annotations

import logging
from typing import Any

from market_intelligence.core.enums import SwingType
from market_intelligence.core.events import SupportResistanceUpdated
from market_intelligence.core.models import SRLevel, SwingPoint
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class SREngine:
    """Clusters active/unbroken swing points into horizontal S&R levels using ATR."""

    def __init__(self, event_bus: IEventBus | None = None, gamma: float = 1.0) -> None:
        self._event_bus = event_bus
        self._gamma = gamma
        # Mapping: (symbol, timeframe) -> list of SRLevel
        self._levels: dict[tuple[str, str], list[SRLevel]] = {}

    def get_levels(self, symbol: str, timeframe: str) -> list[SRLevel]:
        """Get the current support & resistance levels."""
        return self._levels.get((symbol, timeframe), [])

    def evaluate_levels(
        self,
        symbol: str,
        timeframe: str,
        all_swings: list[SwingPoint],
        history: list[Any],
        atr: float,
    ) -> list[SRLevel]:
        """Filter unbroken swing points, cluster them by price, and update S&R levels."""
        key = (symbol, timeframe)
        if not history or not all_swings:
            self._levels[key] = []
            return []

        current_candle = history[-1]

        # 1. Filter unbroken swing points
        # A swing point is broken if any subsequent candle close crosses its price level.
        unbroken_swings: list[SwingPoint] = []
        for swing in all_swings:
            is_broken = False
            swing_idx = swing.index
            # Check all closes from the swing index to the end
            for c in history[swing_idx + 1:]:
                if swing.point_type == SwingType.HIGH and c.close > swing.price:
                    is_broken = True
                    break
                if swing.point_type == SwingType.LOW and c.close < swing.price:
                    is_broken = True
                    break
            if not is_broken:
                unbroken_swings.append(swing)

        if not unbroken_swings:
            self._levels[key] = []
            return []

        # 2. Cluster swings using ATR-normalized threshold
        threshold = self._gamma * atr if atr > 0.0 else 0.0
        # If ATR is not yet calculated or 0, fallback to a small price percentage (e.g. 0.5%)
        if threshold == 0.0:
            threshold = 0.005 * current_candle.close

        sorted_swings = sorted(unbroken_swings, key=lambda s: s.price)
        clusters: list[list[SwingPoint]] = []
        current_cluster: list[SwingPoint] = []

        for swing in sorted_swings:
            if not current_cluster:
                current_cluster.append(swing)
            else:
                mean_price = sum(s.price for s in current_cluster) / len(current_cluster)
                if abs(swing.price - mean_price) <= threshold:
                    current_cluster.append(swing)
                else:
                    clusters.append(current_cluster)
                    current_cluster = [swing]
        if current_cluster:
            clusters.append(current_cluster)

        # 3. Create SRLevels from clusters
        new_levels: list[SRLevel] = []
        for cluster in clusters:
            avg_price = sum(s.price for s in cluster) / len(cluster)
            
            # Type classification: majority vote of swing types
            high_count = sum(1 for s in cluster if s.point_type == SwingType.HIGH)
            low_count = sum(1 for s in cluster if s.point_type == SwingType.LOW)
            
            if high_count > low_count:
                level_type = "RESISTANCE"
            elif low_count > high_count:
                level_type = "SUPPORT"
            else:
                # Tie-breaker: use latest swing type
                latest_swing = max(cluster, key=lambda s: s.index)
                level_type = "RESISTANCE" if latest_swing.point_type == SwingType.HIGH else "SUPPORT"

            sr_level = SRLevel(
                symbol=symbol,
                timeframe=timeframe,
                price=avg_price,
                level_type=level_type,
                touch_count=len(cluster),
                strength=float(len(cluster)),
            )
            new_levels.append(sr_level)

        # 4. Check if levels updated and publish event
        old_levels = self._levels.get(key, [])
        if self._levels_changed(old_levels, new_levels):
            self._levels[key] = new_levels
            self._publish_event(symbol, timeframe, new_levels, current_candle.timestamp)
        else:
            # Maintain old levels to avoid floating point fluctuation replacements
            pass

        return self._levels[key]

    def _levels_changed(self, old: list[SRLevel], new: list[SRLevel]) -> bool:
        if len(old) != len(new):
            return True
        for o, n in zip(old, new):
            if o.level_type != n.level_type or o.touch_count != n.touch_count or abs(o.price - n.price) > 1e-8:
                return True
        return False

    def _publish_event(self, symbol: str, timeframe: str, levels: list[SRLevel], timestamp: Any) -> None:
        if self._event_bus is None:
            return

        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "levels": [lvl.model_dump() for lvl in levels],
            "timestamp": timestamp.isoformat(),
        }

        event = SupportResistanceUpdated(
            source="market_intelligence.sr_engine",
            payload=payload,
        )
        self._event_bus.publish(event)
