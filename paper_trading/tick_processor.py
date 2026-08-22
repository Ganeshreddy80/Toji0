"""Tick Processor validating, ordering, and deduplicating incoming market ticks (Sprint 9B)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
from typing import Dict, Optional, Tuple

from paper_trading.models.market_models import MarketTick

logger = logging.getLogger(__name__)


class TickProcessor:
    """Thread-safe processor validating market ticks and filtering malformed/duplicate/out-of-order data."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._last_timestamps: Dict[str, datetime] = {}
        self._last_tick_signatures: Dict[str, Tuple[datetime, float, float]] = {}

    def validate_and_process(self, tick: MarketTick) -> Optional[MarketTick]:
        """Validate MarketTick, check ordering and duplicate state.

        Returns valid MarketTick, or None if tick is malformed, duplicate, or out-of-order.
        """
        if not tick or not isinstance(tick, MarketTick):
            logger.warning("Rejected invalid tick object: %s", tick)
            return None

        if not tick.symbol or not isinstance(tick.symbol, str) or not tick.symbol.strip():
            logger.warning("Rejected tick with empty or invalid symbol: %s", tick.symbol)
            return None

        if tick.price <= 0.0:
            logger.warning("Rejected tick with non-positive price: %s", tick.price)
            return None

        if tick.volume < 0.0:
            logger.warning("Rejected tick with negative volume: %s", tick.volume)
            return None

        ts = tick.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        with self._lock:
            symbol = tick.symbol
            last_ts = self._last_timestamps.get(symbol)
            last_sig = self._last_tick_signatures.get(symbol)

            current_sig = (ts, tick.price, tick.volume)

            # 1. Duplicate check
            if last_sig and current_sig == last_sig:
                logger.debug("Rejected duplicate tick for %s at %s", symbol, ts)
                return None

            # 2. Out-of-order check
            if last_ts and ts < last_ts:
                logger.warning("Rejected out-of-order tick for %s (tick ts %s < last ts %s)", symbol, ts, last_ts)
                return None

            self._last_timestamps[symbol] = ts
            self._last_tick_signatures[symbol] = current_sig

            if ts != tick.timestamp:
                return MarketTick(
                    symbol=tick.symbol,
                    price=tick.price,
                    volume=tick.volume,
                    timestamp=ts,
                )
            return tick

    def reset_symbol_state(self, symbol: str) -> None:
        """Reset sequence state for a symbol."""
        with self._lock:
            self._last_timestamps.pop(symbol, None)
            self._last_tick_signatures.pop(symbol, None)

    def clear(self) -> None:
        """Clear all tracking state."""
        with self._lock:
            self._last_timestamps.clear()
            self._last_tick_signatures.clear()
