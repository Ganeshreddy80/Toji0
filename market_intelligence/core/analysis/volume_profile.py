"""Volume Profile Engine for calculating horizontal volume profiles, POC, VAH and VAL."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from market_intelligence.core.events import VolumeProfileUpdated
from market_intelligence.core.models import VolumeProfileAnalysis
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class VolumeProfileEngine:
    """Calculates POC, VAH, VAL, and acceptance/rejection zones over a rolling candle window."""

    def __init__(self, event_bus: IEventBus | None = None, window: int = 100) -> None:
        self._event_bus = event_bus
        self._window = window
        self._candles: dict[tuple[str, str], list[Any]] = {}

    def calculate_volume_profile(self, candle: Any) -> VolumeProfileAnalysis:
        """Process a new candle and compute rolling volume profile analysis."""
        symbol = candle.symbol
        timeframe = candle.interval
        key = (symbol, timeframe)

        if key not in self._candles:
            self._candles[key] = []

        history = self._candles[key]
        history.append(candle)
        if len(history) > self._window:
            history.pop(0)

        n = len(history)
        closes = [c.close for c in history]
        highs = [c.high for c in history]
        lows = [c.low for c in history]

        lowest_low = min(lows)
        highest_high = max(highs)
        price_range = highest_high - lowest_low

        # Default fallback
        poc = candle.close
        vah = candle.close
        val = candle.close
        hvn = [candle.close]
        lvn = [candle.close]
        acceptance_zones = [(lowest_low, highest_high)]
        rejection_zones = []

        if price_range > 0.0:
            bins_count = 10
            bin_size = price_range / bins_count
            bin_volumes = [0.0] * bins_count
            bin_bounds = []

            for i in range(bins_count):
                lower = lowest_low + i * bin_size
                upper = lower + bin_size
                bin_bounds.append((lower, upper))

            # Distribute volume
            total_vol = 0.0
            for c in history:
                for idx, (lower, upper) in enumerate(bin_bounds):
                    if lower <= c.close <= upper:
                        bin_volumes[idx] += c.volume
                        total_vol += c.volume
                        break

            # 1. POC
            max_idx = bin_volumes.index(max(bin_volumes))
            poc = bin_bounds[max_idx][0] + (bin_size / 2.0)

            # 2. Value Area (70% of total volume centered around POC)
            target_va_vol = total_vol * 0.70
            va_indices = {max_idx}
            accumulated_vol = bin_volumes[max_idx]

            while accumulated_vol < target_va_vol and len(va_indices) < bins_count:
                # Compare next neighbor indices
                left_idx = min(va_indices) - 1
                right_idx = max(va_indices) + 1

                left_vol = bin_volumes[left_idx] if left_idx >= 0 else -1.0
                right_vol = bin_volumes[right_idx] if right_idx < bins_count else -1.0

                if left_vol >= right_vol and left_vol >= 0.0:
                    va_indices.add(left_idx)
                    accumulated_vol += left_vol
                elif right_vol >= 0.0:
                    va_indices.add(right_idx)
                    accumulated_vol += right_vol
                else:
                    break

            min_va_idx = min(va_indices)
            max_va_idx = max(va_indices)
            val = bin_bounds[min_va_idx][0]
            vah = bin_bounds[max_va_idx][1]

            # 3. High and Low Volume Nodes
            mean_bin_vol = sum(bin_volumes) / bins_count
            hvn = []
            lvn = []
            acceptance_zones = []
            rejection_zones = []

            for idx, (lower, upper) in enumerate(bin_bounds):
                center = lower + (bin_size / 2.0)
                if bin_volumes[idx] >= mean_bin_vol:
                    hvn.append(center)
                    acceptance_zones.append((lower, upper))
                else:
                    lvn.append(center)
                    rejection_zones.append((lower, upper))

        analysis = VolumeProfileAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            poc=poc,
            vah=vah,
            val=val,
            high_volume_nodes=hvn,
            low_volume_nodes=lvn,
            acceptance_zones=acceptance_zones,
            rejection_zones=rejection_zones,
            timestamp=candle.timestamp
        )

        self._publish_event(analysis)
        return analysis

    def _publish_event(self, analysis: VolumeProfileAnalysis) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": analysis.symbol,
            "timeframe": analysis.timeframe,
            "poc": analysis.poc,
            "vah": analysis.vah,
            "val": analysis.val,
            "high_volume_nodes": analysis.high_volume_nodes,
            "low_volume_nodes": analysis.low_volume_nodes,
            "acceptance_zones": analysis.acceptance_zones,
            "rejection_zones": analysis.rejection_zones,
            "timestamp": analysis.timestamp.isoformat()
        }
        event = VolumeProfileUpdated(
            source="market_intelligence.volume_profile_engine",
            payload=payload
        )
        self._event_bus.publish(event)
