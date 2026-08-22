"""Unit tests for the Data Providers framework."""

from __future__ import annotations

from datetime import UTC, datetime
import pytest

from data.providers.implementations import BinanceProvider, NewsProvider
from toji_platform.core.types import HealthStatus, ModuleState


def test_binance_provider_lifecycle():
    provider = BinanceProvider()
    assert provider.name == "Binance"
    assert provider.state == ModuleState.CREATED
    assert provider.plugin_id == "provider_binance"

    provider.initialize(kernel=None)
    assert provider.state == ModuleState.RUNNING
    assert provider.health_check() == HealthStatus.HEALTHY

    # Test historical fetch placeholder
    hist = provider.get_historical_ohlcv(
        symbol="BTC/USDT",
        interval="1m",
        start=datetime.now(UTC),
        end=datetime.now(UTC),
    )
    assert len(hist) == 1
    assert hist[0].symbol == "BTC/USDT"

    provider.shutdown()
    assert provider.state == ModuleState.STOPPED


def test_news_provider_sentiment():
    provider = NewsProvider()
    provider.initialize(kernel=None)

    news = provider.get_latest_news(symbol="BTC/USDT")
    assert len(news) == 1
    assert news[0].associated_symbols == ["BTC/USDT"]
    assert news[0].sentiment == 0.5

    provider.shutdown()
