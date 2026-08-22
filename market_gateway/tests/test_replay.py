"""Unit tests for the Market Replay Engine."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

import pytest

from toji_platform.core.event_bus.bus import InMemoryEventBus
from market_gateway.replay.engine import MarketReplayEngine


def test_replay_engine_flow(tmp_path):
    async def _run_test():
        event_bus = InMemoryEventBus()
        replay_engine = MarketReplayEngine(event_bus=event_bus, dataset_dir=str(tmp_path))

        # Seed mock dataset JSON
        dataset_file = tmp_path / "BTCUSDT_ohlcv_1m.json"
        now = datetime.now(UTC)
        mock_records = [
            {
                "symbol": "BTCUSDT",
                "timestamp": (now - timedelta(minutes=2)).isoformat(),
                "open": 95000.0,
                "high": 95100.0,
                "low": 94900.0,
                "close": 95050.0,
                "volume": 1.5,
                "interval": "1m",
            },
            {
                "symbol": "BTCUSDT",
                "timestamp": (now - timedelta(minutes=1)).isoformat(),
                "open": 95050.0,
                "high": 95200.0,
                "low": 95000.0,
                "close": 95150.0,
                "volume": 2.1,
                "interval": "1m",
            },
        ]

        with open(dataset_file, "w") as f:
            json.dump(mock_records, f)

        # Subscribe to Event Bus
        events_received = []
        event_bus.subscribe("system.market_data_updated", events_received.append)

        # Run replay
        count = await replay_engine.replay_ohlcv(
            symbol="BTCUSDT",
            interval="1m",
            speed_factor=0.0,  # immediate
        )

        assert count == 2
        assert len(events_received) == 2
        assert events_received[0].payload["symbol"] == "BTCUSDT"
        assert events_received[0].payload["data"]["close"] == 95050.0
        assert events_received[1].payload["data"]["close"] == 95150.0

    import asyncio
    asyncio.run(_run_test())
