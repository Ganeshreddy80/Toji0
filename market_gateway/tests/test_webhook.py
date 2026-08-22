"""Unit tests for the TradingView webhook endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from toji_platform.core.event_bus.bus import InMemoryEventBus
from market_gateway.providers.tradingview.webhook import TradingViewWebhookReceiver


def test_tradingview_webhook_candle():
    event_bus = InMemoryEventBus()
    receiver = TradingViewWebhookReceiver(event_bus=event_bus)

    app = FastAPI()
    app.include_router(receiver.router)
    client = TestClient(app)

    # Track published events
    received_events = []
    event_bus.subscribe("system.market_data_updated", received_events.append)

    # Post mock TV alert
    alert_payload = {
        "symbol": "BTCUSDT",
        "price": 95300.0,
        "volume": 15.4,
        "interval": "1m",
    }
    response = client.post("/webhooks/tradingview", json=alert_payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    assert len(received_events) == 1
    event = received_events[0]
    assert event.payload["symbol"] == "BTCUSDT"
    assert event.payload["data_type"] == "ohlcv"
    assert event.payload["data"]["close"] == 95300.0


def test_tradingview_webhook_news():
    event_bus = InMemoryEventBus()
    receiver = TradingViewWebhookReceiver(event_bus=event_bus)

    app = FastAPI()
    app.include_router(receiver.router)
    client = TestClient(app)

    received_events = []
    event_bus.subscribe("system.market_data_updated", received_events.append)

    # Post mock news alert
    alert_payload = {
        "symbol": "ETHUSDT",
        "title": "ETH Breakout",
        "message": "Ethereum crossed key resistance at 3500",
        "sentiment": 0.8,
    }
    response = client.post("/webhooks/tradingview", json=alert_payload)
    assert response.status_code == 200

    assert len(received_events) == 1
    event = received_events[0]
    assert event.payload["symbol"] == "ETHUSDT"
    assert event.payload["data_type"] == "news"
    assert event.payload["data"]["sentiment"] == 0.8
