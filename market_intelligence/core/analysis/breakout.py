"""Break Engine for detecting Break of Structure (BOS) and Change of Character (CHoCH)."""

from __future__ import annotations

import logging
from typing import Any

from market_intelligence.core.enums import SwingType
from market_intelligence.core.events import (
    BreakOfStructureDetected,
    ChangeOfCharacterDetected,
)
from market_intelligence.core.models import BOSRecord, CHoCHRecord, StructurePoint
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class BreakEngine:
    """Detects breakouts of prior swing structures (BOS & CHoCH) on candle close."""

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus
        # Tracking: (symbol, timeframe) -> last broken swing point index
        self._last_broken_high_idx: dict[tuple[str, str], int] = {}
        self._last_broken_low_idx: dict[tuple[str, str], int] = {}

        self._bos_history: dict[tuple[str, str], list[BOSRecord]] = {}
        self._choch_history: dict[tuple[str, str], list[CHoCHRecord]] = {}

    def get_bos_history(self, symbol: str, timeframe: str) -> list[BOSRecord]:
        return self._bos_history.get((symbol, timeframe), [])

    def get_choch_history(self, symbol: str, timeframe: str) -> list[CHoCHRecord]:
        return self._choch_history.get((symbol, timeframe), [])

    def evaluate_breakouts(
        self,
        symbol: str,
        timeframe: str,
        trend_direction: str,  # "BULLISH", "BEARISH", "RANGING", "UNKNOWN"
        structure_history: list[StructurePoint],
        current_candle: Any,
    ) -> tuple[BOSRecord | None, CHoCHRecord | None]:
        """Check the current candle close price against confirmed swing boundaries."""
        key = (symbol, timeframe)

        highs = [
            p.swing_point
            for p in structure_history
            if p.swing_point.point_type == SwingType.HIGH
        ]
        lows = [
            p.swing_point
            for p in structure_history
            if p.swing_point.point_type == SwingType.LOW
        ]

        if not highs or not lows:
            return None, None

        sh_last = highs[-1]
        sl_last = lows[-1]

        close_price = current_candle.close
        timestamp = current_candle.timestamp
        volume = getattr(current_candle, "volume", 0.0)

        bos_record: BOSRecord | None = None
        choch_record: CHoCHRecord | None = None

        if key not in self._bos_history:
            self._bos_history[key] = []
            self._choch_history[key] = []

        last_broken_high = self._last_broken_high_idx.get(key, -1)
        last_broken_low = self._last_broken_low_idx.get(key, -1)

        # Evaluate based on Trend
        if trend_direction == "BULLISH":
            # Bullish BOS: Break high
            if sh_last.index > last_broken_high and close_price > sh_last.price:
                self._last_broken_high_idx[key] = sh_last.index
                bos_record = BOSRecord(
                    symbol=symbol,
                    timeframe=timeframe,
                    level_breached=sh_last.price,
                    direction="UP",
                    break_timestamp=timestamp,
                    volume_at_break=volume,
                )
                self._bos_history[key].append(bos_record)
                self._publish_bos_event(bos_record)

            # Bearish CHoCH: Break low
            elif sl_last.index > last_broken_low and close_price < sl_last.price:
                self._last_broken_low_idx[key] = sl_last.index
                choch_record = CHoCHRecord(
                    symbol=symbol,
                    timeframe=timeframe,
                    level_breached=sl_last.price,
                    direction="BULLISH_TO_BEARISH",
                    trigger_timestamp=timestamp,
                )
                self._choch_history[key].append(choch_record)
                self._publish_choch_event(choch_record)

        elif trend_direction == "BEARISH":
            # Bearish BOS: Break low
            if sl_last.index > last_broken_low and close_price < sl_last.price:
                self._last_broken_low_idx[key] = sl_last.index
                bos_record = BOSRecord(
                    symbol=symbol,
                    timeframe=timeframe,
                    level_breached=sl_last.price,
                    direction="DOWN",
                    break_timestamp=timestamp,
                    volume_at_break=volume,
                )
                self._bos_history[key].append(bos_record)
                self._publish_bos_event(bos_record)

            # Bullish CHoCH: Break high
            elif sh_last.index > last_broken_high and close_price > sh_last.price:
                self._last_broken_high_idx[key] = sh_last.index
                choch_record = CHoCHRecord(
                    symbol=symbol,
                    timeframe=timeframe,
                    level_breached=sh_last.price,
                    direction="BEARISH_TO_BULLISH",
                    trigger_timestamp=timestamp,
                )
                self._choch_history[key].append(choch_record)
                self._publish_choch_event(choch_record)

        return bos_record, choch_record

    def _publish_bos_event(self, record: BOSRecord) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": record.symbol,
            "timeframe": record.timeframe,
            "level_breached": record.level_breached,
            "direction": record.direction,
            "timestamp": record.break_timestamp.isoformat(),
            "volume": record.volume_at_break,
        }
        event = BreakOfStructureDetected(
            source="market_intelligence.break_engine", payload=payload
        )
        self._event_bus.publish(event)

    def _publish_choch_event(self, record: CHoCHRecord) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": record.symbol,
            "timeframe": record.timeframe,
            "level_breached": record.level_breached,
            "direction": record.direction,
            "timestamp": record.trigger_timestamp.isoformat(),
        }
        event = ChangeOfCharacterDetected(
            source="market_intelligence.break_engine", payload=payload
        )
        self._event_bus.publish(event)
