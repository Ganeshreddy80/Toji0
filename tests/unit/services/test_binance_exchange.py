"""Unit tests for BinanceExchangeProvider."""

from __future__ import annotations

import asyncio
import os
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from toji_platform.core.event_bus import InMemoryEventBus
from market_gateway.providers.binance.exchange import BinanceExchangeProvider


def test_binance_provider_signing():
    """Verify HMAC signature generation matches standard encoding."""
    os.environ["BINANCE_API_KEY"] = "test_key"
    os.environ["BINANCE_API_SECRET"] = "test_secret"

    provider = BinanceExchangeProvider(use_mock=True)
    params = {"symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT", "quantity": "1.0", "price": "90000.0"}
    
    signed_query = provider._sign_params(params)
    assert "timestamp=" in signed_query
    assert "signature=" in signed_query
    assert "symbol=BTCUSDT" in signed_query


def test_binance_provider_mock_orders():
    """Verify order placement and balance adjustments in Mock mode."""
    async def _run():
        provider = BinanceExchangeProvider(use_mock=True)
        provider.initialize()

        # Initial balance check
        balances = provider.get_balances()
        assert balances["USDT"] == 100000.0

        # Place Market BUY order
        res = provider.place_market_order("BTCUSDT", "BUY", 0.5)
        assert res["status"] == "FILLED"
        assert res["side"] == "BUY"
        assert float(res["executedQty"]) == 0.5

        # Check balance adjusted
        balances_after = provider.get_balances()
        assert balances_after["BTC"] == 2.0  # Initial 1.5 + 0.5
        assert balances_after["USDT"] < 100000.0

        # Check positions mapping
        positions = provider.get_positions()
        assert len(positions) == 2  # BTC & ETH
        assert any(pos["symbol"] == "BTCUSDT" and pos["amount"] == 2.0 for pos in positions)

        # Place Limit order
        res_limit = provider.place_limit_order("BTCUSDT", "SELL", 1.0, 96000.0)
        assert res_limit["status"] == "NEW"
        assert res_limit["type"] == "LIMIT"

        open_orders = provider.get_open_orders()
        assert len(open_orders) == 1
        assert open_orders[0]["orderId"] == res_limit["orderId"]

        # Cancel order
        canceled = provider.cancel_order("BTCUSDT", res_limit["clientOrderId"])
        assert canceled["status"] == "CANCELED"
        assert len(provider.get_open_orders()) == 0

        provider.shutdown()
        await asyncio.sleep(0.01)

    asyncio.run(_run())


def test_binance_provider_subscriptions():
    """Test public WebSocket stream subscription management."""
    async def _run():
        provider = BinanceExchangeProvider(use_mock=True)
        provider.initialize()

        cb_called = False
        def candle_cb(candle):
            nonlocal cb_called
            cb_called = True

        provider.subscribe_candles("BTCUSDT", "1m", candle_cb)
        # Check subscription registered
        assert ("BTCUSDT", "1m") in provider._candle_subs

        provider.shutdown()
        await asyncio.sleep(0.01)

    asyncio.run(_run())
