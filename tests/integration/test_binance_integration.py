"""Integration tests for Binance Exchange integration with the TOJI platform."""

from __future__ import annotations

import os
import sys
import time
import pytest
import threading
from datetime import datetime, timezone

from toji_platform.runner import LiveRunner
from execution_engine.brokers.binance_broker import BinanceBroker
from market_gateway.providers.binance.exchange import BinanceExchangeProvider
from execution_engine.core.models import Order
from execution_engine.core.enums import OrderSide, OrderType, OrderState, OrderTimeInForce


def test_binance_integration_flow():
    # Pre-populate dummy environment variables for testing
    os.environ["BINANCE_API_KEY"] = "dummy_key"
    os.environ["BINANCE_API_SECRET"] = "dummy_secret"
    os.environ["BINANCE_BASE_URL"] = "https://demo-api.binance.com/api"
    os.environ["BINANCE_WS_URL"] = "wss://demo-stream.binance.com/ws"
    os.environ["TRADING_MODE"] = "paper"
    os.environ["DEFAULT_EXCHANGE"] = "binance"

    config = {
        "market_gateway.provider_mode": "mock",
        "execution.broker": "binance",
        "dashboard.port": 8015,
    }

    runner = LiveRunner(config_overrides=config)

    # Run the live runner in a background thread for 3 seconds
    t = threading.Thread(target=runner.run, args=(["BTC/USDT"], 3.0), daemon=True)
    t.start()

    time.sleep(2.0)

    try:
        container = runner._kernel.container
        assert container.has(BinanceExchangeProvider)

        provider = container.resolve(BinanceExchangeProvider)
        assert provider.use_mock is True  # We forced mock mode for safety

        # 1. Verify balances sync from provider
        broker = BinanceBroker({"container": container})
        broker.connect()
        assert broker.ping() is True

        balances = broker.get_balance()
        assert balances["USDT"] == 100000.0

        # 2. Place a simulated order
        order = Order(
            client_order_id="test-integration-order-1",
            execution_id="exec-1",
            request_id="req-1",
            signal_id="sig-1",
            strategy_id="strat-1",
            position_id="pos-1",
            correlation_id="corr-1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.1,
            time_in_force=OrderTimeInForce.GTC,
            state=OrderState.CREATED,
        )

        res_order = broker.submit_order(order)
        assert res_order.state == OrderState.FILLED
        assert res_order.broker_order_id is not None
        assert res_order.filled_quantity == 0.1

        # Check balance has decreased for USDT and increased for BTC
        new_balances = broker.get_balance()
        assert new_balances["BTC"] == 1.6  # Initial 1.5 + 0.1
        assert new_balances["USDT"] < 100000.0

        broker.disconnect()
    finally:
        t.join(timeout=8.0)
