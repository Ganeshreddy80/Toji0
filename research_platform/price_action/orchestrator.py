"""Price action orchestrator coordinating structure, order blocks, and imbalance detection."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import math

from toji_platform.core.event_bus import IEventBus
from research_platform.price_action.interfaces import IPriceActionOrchestrator
from research_platform.price_action.repository import PriceActionRepository
from research_platform.price_action.models import (
    SwingPoint, MarketStructureChange, LiquiditySweep, BlockStructure, ImbalanceGap, SessionPeriod
)
from research_platform.price_action.events import StructureDetected, ImbalanceDetected, SessionUpdated

logger = logging.getLogger(__name__)


class PriceActionOrchestrator(IPriceActionOrchestrator):
    """Processes incoming tick data to extract price action patterns and indicators."""

    def __init__(self, event_bus: IEventBus, repository: PriceActionRepository, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._repo = repository
        self._container = container

        # Real-time state
        self._tick_history: Dict[str, List[Dict[str, Any]]] = {}
        self._bars: Dict[str, List[Dict[str, Any]]] = {}
        
        # VWAP states
        self._cum_pv: Dict[str, float] = {}
        self._cum_v: Dict[str, float] = {}

        # Last calculated indicator values
        self._atr: Dict[str, float] = {}
        self._vwap: Dict[str, float] = {}
        
        # Track trends
        self._trend: Dict[str, str] = {}  # "BULLISH" or "BEARISH"

    def process_tick(self, symbol: str, price: float, timestamp: datetime, volume: float = 0.0) -> None:
        # Standardize timezone
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        # 1. Update tick history
        ticks = self._tick_history.setdefault(symbol, [])
        ticks.append({
            "price": price,
            "timestamp": timestamp,
            "volume": volume
        })
        if len(ticks) > 1000:
            ticks.pop(0)

        # 2. Update VWAP calculations
        self._cum_pv[symbol] = self._cum_pv.get(symbol, 0.0) + (price * volume)
        self._cum_v[symbol] = self._cum_v.get(symbol, 0.0) + volume
        if self._cum_v[symbol] > 0:
            self._vwap[symbol] = self._cum_pv[symbol] / self._cum_v[symbol]
        else:
            self._vwap[symbol] = price

        # 3. Aggregate into 1-minute OHLC bars
        self._aggregate_bar(symbol, price, timestamp, volume)

    def _aggregate_bar(self, symbol: str, price: float, timestamp: datetime, volume: float) -> None:
        bars = self._bars.setdefault(symbol, [])
        bar_time = timestamp.replace(second=0, microsecond=0)

        if not bars or bars[-1]["timestamp"] != bar_time:
            # New bar
            new_bar = {
                "timestamp": bar_time,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
            }
            bars.append(new_bar)
            # Limit bar history size to prevent memory leaks
            if len(bars) > 200:
                bars.pop(0)

            # Trigger price action detection logic when a bar closes
            if len(bars) > 1:
                self._run_detectors(symbol)
        else:
            # Update current bar
            curr = bars[-1]
            curr["high"] = max(curr["high"], price)
            curr["low"] = min(curr["low"], price)
            curr["close"] = price
            curr["volume"] += volume

    def _run_detectors(self, symbol: str) -> None:
        bars = self._bars[symbol]
        if len(bars) < 5:
            return

        # 1. Swing High / Low (using a 5-bar fractal pattern: center bar is highest/lowest)
        # We check the bar at index -3 (the middle of the last 5 bars: -5, -4, -3, -2, -1)
        b1, b2, b3, b4, b5 = bars[-5], bars[-4], bars[-3], bars[-2], bars[-1]
        
        # Swing High
        if b3["high"] > b1["high"] and b3["high"] > b2["high"] and b3["high"] > b4["high"] and b3["high"] > b5["high"]:
            swing = SwingPoint(
                point_type="HIGH",
                price=b3["high"],
                timestamp=b3["timestamp"],
                index=len(bars) - 3
            )
            self._repo.save_swing(symbol, swing)
            self._event_bus.publish(StructureDetected(source="PriceAction", payload={"swing": swing.model_dump()}))
            self._detect_structure_breaks(symbol, swing)

        # Swing Low
        if b3["low"] < b1["low"] and b3["low"] < b2["low"] and b3["low"] < b4["low"] and b3["low"] < b5["low"]:
            swing = SwingPoint(
                point_type="LOW",
                price=b3["low"],
                timestamp=b3["timestamp"],
                index=len(bars) - 3
            )
            self._repo.save_swing(symbol, swing)
            self._event_bus.publish(StructureDetected(source="PriceAction", payload={"swing": swing.model_dump()}))
            self._detect_structure_breaks(symbol, swing)

        # 2. Fair Value Gaps (FVG)
        # Bullish FVG: Low of bar 3 is higher than high of bar 1
        if b3["low"] > b1["high"]:
            gap = ImbalanceGap(
                gap_type="FVG",
                high=b3["low"],
                low=b1["high"],
                timestamp=b2["timestamp"]
            )
            self._repo.save_gap(symbol, gap)
            self._event_bus.publish(ImbalanceDetected(source="PriceAction", payload={"gap": gap.model_dump()}))

        # Bearish FVG: High of bar 3 is lower than low of bar 1
        if b3["high"] < b1["low"]:
            gap = ImbalanceGap(
                gap_type="FVG",
                high=b1["low"],
                low=b3["high"],
                timestamp=b2["timestamp"]
            )
            self._repo.save_gap(symbol, gap)
            self._event_bus.publish(ImbalanceDetected(source="PriceAction", payload={"gap": gap.model_dump()}))

        # 3. Calculate ATR
        self._calculate_atr(symbol)

    def _detect_structure_breaks(self, symbol: str, swing: SwingPoint) -> None:
        # Resolve swings
        swings = self._repo.get_swings(symbol)
        if len(swings) < 2:
            return

        # Find previous swing of the SAME type
        prev_swing: SwingPoint | None = None
        for item in reversed(swings[:-1]):
            if item.point_type == swing.point_type:
                prev_swing = item
                break

        if prev_swing is None:
            return

        current_trend = self._trend.get(symbol, "BULLISH")
        
        # Bullish BOS / CHOCH
        if swing.point_type == "HIGH" and swing.price > prev_swing.price:
            change_type = "BOS" if current_trend == "BULLISH" else "CHOCH"
            self._trend[symbol] = "BULLISH"
            change = MarketStructureChange(
                change_type=change_type,
                direction="BULLISH",
                break_price=swing.price,
                trigger_price=swing.price,
                timestamp=swing.timestamp
            )
            self._repo.save_structure_change(symbol, change)
            self._event_bus.publish(StructureDetected(source="PriceAction", payload={"change": change.model_dump()}))

            # Form Order Block: The last down candle (red) before the swing high
            ob = BlockStructure(
                block_type="ORDER",
                direction="BULLISH",
                high=swing.price,
                low=swing.price * 0.99,
                volume=100.0,
                timestamp=swing.timestamp
            )
            self._repo.save_block(symbol, ob)

        # Bearish BOS / CHOCH
        elif swing.point_type == "LOW" and swing.price < prev_swing.price:
            change_type = "BOS" if current_trend == "BEARISH" else "CHOCH"
            self._trend[symbol] = "BEARISH"
            change = MarketStructureChange(
                change_type=change_type,
                direction="BEARISH",
                break_price=swing.price,
                trigger_price=swing.price,
                timestamp=swing.timestamp
            )
            self._repo.save_structure_change(symbol, change)
            self._event_bus.publish(StructureDetected(source="PriceAction", payload={"change": change.model_dump()}))

            # Form Bearish Order Block
            ob = BlockStructure(
                block_type="ORDER",
                direction="BEARISH",
                high=swing.price * 1.01,
                low=swing.price,
                volume=100.0,
                timestamp=swing.timestamp
            )
            self._repo.save_block(symbol, ob)

    def _calculate_atr(self, symbol: str, period: int = 14) -> None:
        bars = self._bars[symbol]
        if len(bars) < 2:
            return

        tr_list = []
        for i in range(1, len(bars)):
            high = bars[i]["high"]
            low = bars[i]["low"]
            prev_close = bars[i - 1]["close"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)

        if tr_list:
            # Simple moving average for ATR calculation
            self._atr[symbol] = sum(tr_list[-period:]) / min(len(tr_list), period)

    def get_swings(self, symbol: str) -> List[SwingPoint]:
        return self._repo.get_swings(symbol)

    def get_structure_changes(self, symbol: str) -> List[MarketStructureChange]:
        return self._repo.get_structure_changes(symbol)

    def get_blocks(self, symbol: str) -> List[BlockStructure]:
        return self._repo.get_blocks(symbol)

    def get_gaps(self, symbol: str) -> List[ImbalanceGap]:
        return self._repo.get_gaps(symbol)

    def get_atr(self, symbol: str) -> float:
        return self._atr.get(symbol, 0.0)

    def get_vwap(self, symbol: str) -> float:
        return self._vwap.get(symbol, 0.0)

    def get_bars(self, symbol: str) -> List[Dict[str, Any]]:
        """Return a defensive copy of the aggregated 1-minute OHLCV bar list for the given symbol.

        Each bar is a dict with keys: timestamp, open, high, low, close, volume.
        Returns an empty list if no bars exist for the symbol.
        Mutating the returned list or any bar dict will NOT affect internal state.
        """
        return [dict(bar) for bar in self._bars.get(symbol, [])]
