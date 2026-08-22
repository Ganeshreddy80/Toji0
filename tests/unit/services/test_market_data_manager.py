"""Unit tests for Market Data Manager service."""

from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.events import BaseEvent
from toji_platform.services.market_data_manager import MarketDataManager


def test_market_data_manager_subscription():
    bus = InMemoryEventBus()
    gateway = MagicMock()
    
    # 5 subs per second max rate limit
    mdm = MarketDataManager(event_bus=bus, market_gateway=gateway, rate_limit_per_sec=5.0)
    mdm.start()

    # Subscribe to candles
    success = mdm.subscribe("BTC/USDT", "ohlcv", "1m")
    assert success is True
    gateway.subscribe_candles.assert_called_once_with("BTC/USDT", "1m")

    # Subscribe to trades
    success_trade = mdm.subscribe("BTC/USDT", "trade")
    assert success_trade is True
    gateway.subscribe_trades.assert_called_once_with("BTC/USDT")

    # Verify tracked subscriptions
    subs = mdm.get_subscriptions()
    assert "BTC/USDT:ohlcv:1m" in subs
    assert "BTC/USDT:trade:1m" in subs
    assert subs["BTC/USDT:ohlcv:1m"]["status"] == "active"

    mdm.stop()


def test_market_data_manager_wildcard_heartbeat():
    bus = InMemoryEventBus()
    gateway = MagicMock()
    mdm = MarketDataManager(event_bus=bus, market_gateway=gateway, stale_threshold_sec=0.5)
    mdm.start()

    mdm.subscribe("BTC/USDT", "ohlcv", "1m")
    subs = mdm.get_subscriptions()
    initial_hb = datetime.fromisoformat(subs["BTC/USDT:ohlcv:1m"]["last_heartbeat"])

    # Wait and check that we detect stale/reconnect
    time.sleep(0.6)
    
    # Simulate a market data event to refresh heartbeat
    @dataclass(frozen=True)
    class MarketCandleEvent(BaseEvent):
        pass

    event = MarketCandleEvent(
        source="test_gateway",
        payload={
            "symbol": "BTC/USDT",
            "candle": {"symbol": "BTC/USDT", "interval": "1m", "close": 50000.0}
        }
    )
    bus.publish(event)

    subs = mdm.get_subscriptions()
    new_hb = datetime.fromisoformat(subs["BTC/USDT:ohlcv:1m"]["last_heartbeat"])
    assert new_hb > initial_hb

    mdm.stop()


from dataclasses import dataclass
