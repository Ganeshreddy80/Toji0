"""Historical market event replay engine for testing strategies."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, UTC
from typing import Any

from data.schemas.market_data import OHLCV, Trade
from market_gateway.core.events import MarketCandleEvent, MarketTradeEvent
from market_gateway.validation.validator import MarketDataValidator
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class MarketReplayEngine:
    """Replays historical datasets through standard gateway pipes to the Event Bus."""

    def __init__(
        self,
        event_bus: IEventBus,
        validator: MarketDataValidator | None = None,
        dataset_dir: str = "data/datasets",
    ) -> None:
        self.event_bus = event_bus
        self.validator = validator or MarketDataValidator()
        self.dataset_dir = dataset_dir
        self._active_replay = False

    async def replay_ohlcv(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        speed_factor: float = 1.0,  # 1.0 = real-time delta delay, 0.0 = push instantly
    ) -> int:
        """Read saved candles from dataset, filter by date range, and publish.

        Returns:
            int: Number of events published.
        """
        file_path = os.path.join(self.dataset_dir, f"{symbol}_ohlcv_{interval}.json")
        if not os.path.exists(file_path):
            logger.error("Dataset file %s does not exist for replay.", file_path)
            return 0

        try:
            with open(file_path) as f:
                records = json.load(f)
        except Exception as e:
            logger.error("Failed to read replay file: %s", e)
            return 0

        # Filter and prepare rows
        events_to_replay = []
        for r in records:
            # Parse timestamp
            ts = r.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            
            # Compare time bounds safely
            if start_time and ts < start_time:
                continue
            if end_time and ts > end_time:
                continue
            
            # Create standard OHLCV
            ohlcv = OHLCV(
                symbol=r["symbol"],
                timestamp=ts.replace(tzinfo=UTC),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r["volume"]),
                interval=r["interval"],
            )
            events_to_replay.append(ohlcv)

        if not events_to_replay:
            logger.warning("No events match the replay time window.")
            return 0

        # Sort by timestamp to preserve order
        events_to_replay.sort(key=lambda x: x.timestamp)
        logger.info("Starting replay of %d candles for %s", len(events_to_replay), symbol)

        self._active_replay = True
        count = 0
        last_ts = None

        for ohlcv in events_to_replay:
            if not self._active_replay:
                break

            # Handle delay if speed_factor is positive
            if speed_factor > 0.0 and last_ts is not None:
                delta_sec = (ohlcv.timestamp - last_ts).total_seconds()
                delay = (delta_sec / speed_factor)
                # Cap the maximum delay to prevent blocking tests indefinitely
                delay = min(delay, 2.0)
                await asyncio.sleep(delay)

            # Validate
            errors = self.validator.validate_event(ohlcv)
            if errors:
                logger.error("Replay data validation failed for %s at %s: %s", symbol, ohlcv.timestamp, errors)
                continue

            # Publish event onto the bus
            event = MarketCandleEvent(
                source="replay_engine",
                payload={
                    "symbol": ohlcv.symbol,
                    "data_type": "ohlcv",
                    "prices": [ohlcv.close],
                    "volumes": [ohlcv.volume],
                    "data": ohlcv.model_dump(),
                },
            )
            self.event_bus.publish(event)
            count += 1
            last_ts = ohlcv.timestamp

        self._active_replay = False
        logger.info("Finished replaying %d candles.", count)
        return count

    def stop(self) -> None:
        """Cancel active playback."""
        self._active_replay = False
