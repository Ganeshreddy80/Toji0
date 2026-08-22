"""Tests for the central UniverseManager — full pipeline integration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable
from unittest.mock import MagicMock

from data.schemas.market_data import OHLCV, OrderBookSnapshot, Trade
from market_gateway.core.interfaces import IMarketGatewayProvider
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.types import HealthStatus, ModuleState
from universe.core.manager import UniverseManager
from universe.core.models import Tier, UniverseConfig
from universe.discovery.engine import DiscoveryEngine
from universe.providers.base import BaseDiscoveryProvider


# ── Mock Gateway Provider ──────────────────────────────────────────────


class MockGatewayProvider(IMarketGatewayProvider):
    """Minimal mock gateway provider for integration tests."""

    def __init__(self) -> None:
        self._name = "MockExchange"

    @property
    def name(self) -> str:
        return self._name

    def initialize(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def check_health(self) -> dict[str, Any]:
        return {"status": "connected"}

    def subscribe_candles(self, symbol: str, interval: str, callback: Callable[[OHLCV], None]) -> None:
        pass

    def subscribe_trades(self, symbol: str, callback: Callable[[Trade], None]) -> None:
        pass

    def subscribe_order_book(self, symbol: str, callback: Callable[[OrderBookSnapshot], None]) -> None:
        pass

    def get_historical_candles(self, symbol: str, interval: str, start: datetime, end: datetime) -> list[OHLCV]:
        return []

    def get_exchange_info(self) -> dict[str, Any]:
        return {
            "symbols": [
                {"symbol": "BTCUSDT", "status": "TRADING", "baseAsset": "BTC", "quoteAsset": "USDT"},
                {"symbol": "ETHUSDT", "status": "TRADING", "baseAsset": "ETH", "quoteAsset": "USDT"},
                {"symbol": "SOLUSDT", "status": "TRADING", "baseAsset": "SOL", "quoteAsset": "USDT"},
                {"symbol": "ADAUSDT", "status": "TRADING", "baseAsset": "ADA", "quoteAsset": "USDT"},
                {"symbol": "DOTUSDT", "status": "TRADING", "baseAsset": "DOT", "quoteAsset": "USDT"},
                {"symbol": "AVAXUSDT", "status": "TRADING", "baseAsset": "AVAX", "quoteAsset": "USDT"},
                {"symbol": "LINKUSDT", "status": "TRADING", "baseAsset": "LINK", "quoteAsset": "USDT"},
                {"symbol": "MATICUSDT", "status": "TRADING", "baseAsset": "MATIC", "quoteAsset": "USDT"},
                {"symbol": "UNIUSDT", "status": "TRADING", "baseAsset": "UNI", "quoteAsset": "USDT"},
                {"symbol": "AAVEUSDT", "status": "TRADING", "baseAsset": "AAVE", "quoteAsset": "USDT"},
            ]
        }

    def get_symbols(self) -> list[str]:
        return [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOTUSDT",
            "AVAXUSDT", "LINKUSDT", "MATICUSDT", "UNIUSDT", "AAVEUSDT",
        ]


# ── Mock Event Bus ─────────────────────────────────────────────────────


class RecordingEventBus(IEventBus):
    """Event bus that records all published events for assertions."""

    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event) -> None:
        self.published.append(event)

    def subscribe(self, event_type: str, handler) -> None:
        pass

    def unsubscribe(self, event_type: str, handler) -> None:
        pass

    def has_subscribers(self, event_type: str) -> bool:
        return False

    def clear(self) -> None:
        self.published.clear()


# ── Integration Tests ──────────────────────────────────────────────────


class TestUniverseManager:
    """Test the full UniverseManager pipeline."""

    def _build_manager(self) -> tuple[UniverseManager, RecordingEventBus]:
        bus = RecordingEventBus()
        config = UniverseConfig(
            min_volume_24h_usd=0.0,  # Disable volume filter for test
            min_price_usd=0.0,       # Disable price filter for test
        )

        discovery = DiscoveryEngine()
        discovery.register_provider(BaseDiscoveryProvider(MockGatewayProvider()))

        manager = UniverseManager(
            event_bus=bus,
            discovery_engine=discovery,
            config=config,
        )
        return manager, bus

    def test_plugin_properties(self) -> None:
        manager, _ = self._build_manager()
        assert manager.plugin_id == "universe_manager"
        assert manager.name == "Universe Manager"
        assert manager.version == "1.0.0"
        assert "market_gateway" in manager.dependencies

    def test_lifecycle_initialize_and_shutdown(self) -> None:
        manager, _ = self._build_manager()
        assert manager.state == ModuleState.CREATED
        manager.initialize()
        assert manager.state == ModuleState.RUNNING
        manager.shutdown()
        assert manager.state == ModuleState.STOPPED

    def test_health_check_before_init(self) -> None:
        manager, _ = self._build_manager()
        assert manager.health_check() == HealthStatus.UNHEALTHY

    def test_run_scan_produces_snapshot(self) -> None:
        manager, bus = self._build_manager()
        manager.initialize()
        snapshot = manager.run_scan()

        assert snapshot is not None
        assert snapshot.total_discovered == 10
        assert snapshot.total_after_filter == 10  # No filters active
        assert len(snapshot.assets) == 10

    def test_run_scan_assigns_tiers(self) -> None:
        manager, _ = self._build_manager()
        manager.initialize()
        snapshot = manager.run_scan()

        tiers = {a.rank.tier for a in snapshot.assets if a.rank}
        assert len(tiers) > 0
        # Should have at least S and C tiers
        assert Tier.S in tiers

    def test_run_scan_publishes_universe_updated(self) -> None:
        manager, bus = self._build_manager()
        manager.initialize()
        manager.run_scan()

        event_types = [
            e.event_type for e in bus.published
            if hasattr(e, "event_type")
        ]
        assert "system.universe_updated" in event_types

    def test_run_scan_publishes_asset_discovered_events(self) -> None:
        manager, bus = self._build_manager()
        manager.initialize()
        manager.run_scan()

        discovered_events = [
            e for e in bus.published
            if hasattr(e, "event_type") and e.event_type == "system.asset_discovered"
        ]
        assert len(discovered_events) == 10  # All new on first scan

    def test_second_scan_detects_drift(self) -> None:
        manager, bus = self._build_manager()
        manager.initialize()

        # First scan
        manager.run_scan()
        bus.published.clear()

        # Second scan — no new discoveries expected
        snapshot2 = manager.run_scan()
        discovered_events = [
            e for e in bus.published
            if hasattr(e, "event_type") and e.event_type == "system.asset_discovered"
        ]
        # All assets were already known, so no new discovery events
        assert len(discovered_events) == 0

    def test_watchlists_populated_after_scan(self) -> None:
        manager, _ = self._build_manager()
        manager.initialize()
        snapshot = manager.run_scan()

        primary = manager.watchlist_manager.get_watchlist("primary")
        assert primary is not None
        assert len(primary.entries) > 0

    def test_snapshot_persisted_to_repository(self) -> None:
        manager, _ = self._build_manager()
        manager.initialize()
        manager.run_scan()

        latest = manager._repository.load_latest_snapshot()
        assert latest is not None
        assert latest.total_discovered == 10

    def test_health_check_after_scan(self) -> None:
        manager, _ = self._build_manager()
        manager.initialize()
        manager.run_scan()
        assert manager.health_check() == HealthStatus.HEALTHY

    def test_detailed_health_metrics(self) -> None:
        manager, _ = self._build_manager()
        manager.initialize()
        manager.run_scan()
        metrics = manager.get_detailed_health()
        assert metrics["status"] == "healthy"
        assert metrics["total_discovered"] == 10
