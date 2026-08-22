"""Unit tests for the Binance reference provider implementation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from data.schemas.market_data import OHLCV, OrderBookSnapshot, Trade
from market_gateway.providers.binance.client import BinanceGatewayProvider


def test_binance_metadata_discovery():
    async def _run():
        provider = BinanceGatewayProvider(use_mock=True)
        provider.initialize()

        # Discover symbols
        symbols = provider.get_symbols()
        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols

        # Check exchange info
        info = provider.get_exchange_info()
        assert info["timezone"] == "UTC"
        assert len(info["symbols"]) > 0

        provider.shutdown()
        # Give event loop a tick to process task cancels
        await asyncio.sleep(0.01)

    asyncio.run(_run())


def test_binance_historical_candles():
    async def _run():
        provider = BinanceGatewayProvider(use_mock=True)
        provider.initialize()

        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(minutes=5)

        # Fetch
        candles = provider.get_historical_candles("BTCUSDT", "1m", start_time, end_time)
        assert len(candles) > 0
        for bar in candles:
            assert bar.symbol == "BTCUSDT"
            assert bar.interval == "1m"
            assert bar.open > 0.0
            assert bar.high >= bar.low

        provider.shutdown()
        await asyncio.sleep(0.01)

    asyncio.run(_run())


def test_binance_mock_streaming():
    async def _run():
        provider = BinanceGatewayProvider(use_mock=True)
        provider.initialize()

        candles_received = []
        trades_received = []
        depths_received = []

        provider.subscribe_candles("BTCUSDT", "1m", candles_received.append)
        provider.subscribe_trades("BTCUSDT", trades_received.append)
        provider.subscribe_order_book("BTCUSDT", depths_received.append)

        # Allow mock thread to generate some events
        await asyncio.sleep(1.2)

        provider.shutdown()
        await asyncio.sleep(0.01)

        assert len(candles_received) > 0
        assert len(trades_received) > 0
        assert len(depths_received) > 0

        assert isinstance(candles_received[0], OHLCV)
        assert isinstance(trades_received[0], Trade)
        assert isinstance(depths_received[0], OrderBookSnapshot)

    asyncio.run(_run())


def test_binance_certification_fixes():
    import urllib.parse
    import time

    async def _run():
        provider = BinanceGatewayProvider(use_mock=True)
        provider.initialize()

        # 1. Verify clock synchronization offset calculation
        assert provider._time_offset_ms == 0

        # Manually set offset to test signing params
        provider._time_offset_ms = 5000
        params = {"symbol": "BTCUSDT"}
        query = provider._sign_params(params)
        assert "timestamp=" in query
        assert "signature=" in query
        # Extracted timestamp should include offset
        parsed = urllib.parse.parse_qs(query)
        ts = int(parsed["timestamp"][0])
        now_ms = int(time.time() * 1000)
        assert abs(ts - (now_ms + 5000)) < 2000

        # 2. Verify keepalive loop doesn't crash on exception
        provider._listen_key = "test-key"
        orig_ping = provider._ping_listen_key
        call_count = 0
        def failing_ping():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Simulated keepalive connection loss")
            # Do not hit the network during unit tests
            pass
        provider._ping_listen_key = failing_ping

        # Temporarily mock sleep to avoid waiting 20 minutes
        orig_sleep = asyncio.sleep
        async def fast_sleep(sec):
            await orig_sleep(0.001)

        import asyncio as aio_mod
        setattr(aio_mod, "sleep", fast_sleep)

        try:
            # Start keepalive loop task
            task = asyncio.create_task(provider._listen_key_keepalive_loop())
            # Let it run a few cycles using the real unmocked sleep
            await orig_sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        finally:
            setattr(aio_mod, "sleep", orig_sleep)
            provider._ping_listen_key = orig_ping

        # Verify it survived first crash and retried
        assert call_count > 1

        # 3. Verify concurrent thread-safety of subscriptions
        import threading
        threads = []
        errors = []
        def concurrent_subscriber(i):
            try:
                provider.subscribe_candles("BTCUSDT", "1m", lambda x: None)
                provider.subscribe_trades("BTCUSDT", lambda x: None)
                provider.subscribe_order_book("BTCUSDT", lambda x: None)
            except Exception as e:
                errors.append(e)

        for i in range(10):
            t = threading.Thread(target=concurrent_subscriber, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0

        provider.shutdown()
        await asyncio.sleep(0.01)

    asyncio.run(_run())
