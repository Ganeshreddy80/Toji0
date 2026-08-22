"""Tests for the multi-provider discovery engine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable
from unittest.mock import MagicMock

from data.schemas.market_data import OHLCV, OrderBookSnapshot, Trade
from market_gateway.core.interfaces import IMarketGatewayProvider
from universe.core.models import UniverseAsset
from universe.discovery.engine import DiscoveryEngine
from universe.providers.base import BaseDiscoveryProvider
from universe.providers.binance import BinanceDiscoveryProvider


# ── Mock Gateway Provider ──────────────────────────────────────────────


class MockGatewayProvider(IMarketGatewayProvider):
    """Minimal mock that simulates a gateway provider for testing."""

    def __init__(
        self,
        name: str = "MockExchange",
        symbols: list[str] | None = None,
        exchange_info: dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._symbols = symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        self._exchange_info = exchange_info or {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                },
                {
                    "symbol": "ETHUSDT",
                    "status": "TRADING",
                    "baseAsset": "ETH",
                    "quoteAsset": "USDT",
                },
                {
                    "symbol": "SOLUSDT",
                    "status": "TRADING",
                    "baseAsset": "SOL",
                    "quoteAsset": "USDT",
                },
            ]
        }

    @property
    def name(self) -> str:
        return self._name

    def initialize(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def check_health(self) -> dict[str, Any]:
        return {"status": "connected"}

    def subscribe_candles(
        self, symbol: str, interval: str, callback: Callable[[OHLCV], None]
    ) -> None:
        pass

    def subscribe_trades(
        self, symbol: str, callback: Callable[[Trade], None]
    ) -> None:
        pass

    def subscribe_order_book(
        self, symbol: str, callback: Callable[[OrderBookSnapshot], None]
    ) -> None:
        pass

    def get_historical_candles(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[OHLCV]:
        return []

    def get_exchange_info(self) -> dict[str, Any]:
        return self._exchange_info

    def get_symbols(self) -> list[str]:
        return self._symbols


# ── Discovery Tests ────────────────────────────────────────────────────


class TestBaseDiscoveryProvider:
    """Test the base discovery provider."""

    def test_discover_returns_normalized_symbols(self) -> None:
        provider = BaseDiscoveryProvider(MockGatewayProvider())
        assets = provider.discover()
        assert len(assets) > 0
        for asset in assets:
            assert "/" in asset.symbol  # Canonical format: BASE/QUOTE

    def test_discover_sets_exchange_name(self) -> None:
        provider = BaseDiscoveryProvider(MockGatewayProvider(name="TestEx"))
        assets = provider.discover()
        for asset in assets:
            assert "TestEx" in asset.exchanges

    def test_discover_sets_timestamps(self) -> None:
        provider = BaseDiscoveryProvider(MockGatewayProvider())
        assets = provider.discover()
        for asset in assets:
            assert asset.discovered_at is not None
            assert asset.last_updated is not None

    def test_symbol_normalization_with_known_quotes(self) -> None:
        provider = BaseDiscoveryProvider(MockGatewayProvider())
        assert provider._normalize_symbol("BTCUSDT", "BTC", "USDT") == "BTC/USDT"
        assert provider._normalize_symbol("ETHBTC", "ETH", "BTC") == "ETH/BTC"

    def test_symbol_normalization_fallback(self) -> None:
        provider = BaseDiscoveryProvider(MockGatewayProvider())
        # Fallback heuristic when base/quote not provided
        result = provider._normalize_symbol("ADAUSDT", "", "")
        assert result == "ADA/USDT"

    def test_is_available_when_connected(self) -> None:
        provider = BaseDiscoveryProvider(MockGatewayProvider())
        assert provider.is_available() is True


class TestBinanceDiscoveryProvider:
    """Test Binance-specific metadata parsing."""

    def test_parse_exchange_info_extracts_metadata(self) -> None:
        exchange_info = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "filters": [
                        {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                        {"filterType": "LOT_SIZE", "stepSize": "0.00001"},
                        {"filterType": "MIN_NOTIONAL", "minNotional": "10.0"},
                    ],
                }
            ]
        }
        gateway = MockGatewayProvider(exchange_info=exchange_info)
        provider = BinanceDiscoveryProvider(gateway)
        result = provider._parse_exchange_info(exchange_info)

        assert "BTCUSDT" in result
        meta = result["BTCUSDT"]
        assert meta["base_asset"] == "BTC"
        assert meta["quote_asset"] == "USDT"
        assert meta["tick_size"] == 0.01
        assert meta["lot_size"] == 0.00001
        assert meta["min_notional"] == 10.0

    def test_discover_integrates_metadata(self) -> None:
        exchange_info = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "filters": [],
                },
            ]
        }
        gateway = MockGatewayProvider(
            symbols=["BTCUSDT"],
            exchange_info=exchange_info,
        )
        provider = BinanceDiscoveryProvider(gateway)
        assets = provider.discover()
        assert len(assets) == 1
        assert assets[0].symbol == "BTC/USDT"
        assert assets[0].base_asset == "BTC"


class TestDiscoveryEngine:
    """Test the multi-provider aggregation engine."""

    def _make_provider(
        self, name: str, symbols: list[str]
    ) -> BaseDiscoveryProvider:
        exchange_info = {
            "symbols": [
                {
                    "symbol": s,
                    "status": "TRADING",
                    "baseAsset": s[:-4] if s.endswith("USDT") else s[:3],
                    "quoteAsset": "USDT" if s.endswith("USDT") else s[3:],
                }
                for s in symbols
            ]
        }
        return BaseDiscoveryProvider(
            MockGatewayProvider(name=name, symbols=symbols, exchange_info=exchange_info)
        )

    def test_discover_all_aggregates_providers(self) -> None:
        engine = DiscoveryEngine()
        engine.register_provider(
            self._make_provider("Exchange1", ["BTCUSDT", "ETHUSDT"])
        )
        engine.register_provider(
            self._make_provider("Exchange2", ["SOLUSDT", "ADAUSDT"])
        )
        assets = engine.discover_all()
        symbols = {a.symbol for a in assets}
        assert "BTC/USDT" in symbols
        assert "ETH/USDT" in symbols
        assert "SOL/USDT" in symbols
        assert "ADA/USDT" in symbols

    def test_deduplication_merges_exchanges(self) -> None:
        engine = DiscoveryEngine()
        engine.register_provider(
            self._make_provider("Binance", ["BTCUSDT"])
        )
        engine.register_provider(
            self._make_provider("Bybit", ["BTCUSDT"])
        )
        assets = engine.discover_all()

        btc_assets = [a for a in assets if a.symbol == "BTC/USDT"]
        assert len(btc_assets) == 1
        assert "Binance" in btc_assets[0].exchanges
        assert "Bybit" in btc_assets[0].exchanges

    def test_empty_providers_returns_empty(self) -> None:
        engine = DiscoveryEngine()
        assets = engine.discover_all()
        assert assets == []

    def test_provider_count(self) -> None:
        engine = DiscoveryEngine()
        assert engine.provider_count == 0
        engine.register_provider(
            self._make_provider("Ex1", ["BTCUSDT"])
        )
        assert engine.provider_count == 1
