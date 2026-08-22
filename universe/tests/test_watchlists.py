"""Tests for the watchlist manager."""

from __future__ import annotations

from unittest.mock import MagicMock

from toji_platform.core.event_bus.interfaces import IEventBus
from universe.core.models import (
    AssetRank,
    AssetScore,
    Tier,
    UniverseAsset,
    WatchlistType,
)
from universe.watchlists.manager import WatchlistManager


def _make_ranked_asset(
    symbol: str, tier: Tier, position: int, composite: float = 50.0,
    promoted: bool = False,
) -> UniverseAsset:
    return UniverseAsset(
        symbol=symbol,
        base_asset=symbol.split("/")[0],
        quote_asset="USDT",
        score=AssetScore(composite_score=composite),
        rank=AssetRank(tier=tier, position=position, promoted=promoted),
    )


class TestWatchlistManager:
    """Test watchlist CRUD and auto-rebalancing."""

    def test_default_watchlists_created(self) -> None:
        manager = WatchlistManager()
        names = {w.name for w in manager.list_watchlists()}
        assert "primary" in names
        assert "secondary" in names
        assert "monitoring" in names

    def test_create_watchlist(self) -> None:
        manager = WatchlistManager()
        wl = manager.create_watchlist("custom", watchlist_type="manual")
        assert wl.name == "custom"
        assert wl.watchlist_type == WatchlistType.MANUAL

    def test_get_watchlist(self) -> None:
        manager = WatchlistManager()
        wl = manager.get_watchlist("primary")
        assert wl is not None
        assert wl.name == "primary"

    def test_get_nonexistent_returns_none(self) -> None:
        manager = WatchlistManager()
        assert manager.get_watchlist("nonexistent") is None

    def test_add_asset_to_watchlist(self) -> None:
        manager = WatchlistManager()
        manager.create_watchlist("test", watchlist_type="manual")
        manager.add_asset("test", "BTC/USDT", reason="High conviction")
        wl = manager.get_watchlist("test")
        assert len(wl.entries) == 1
        assert wl.entries[0].symbol == "BTC/USDT"
        assert wl.entries[0].reason == "High conviction"

    def test_add_duplicate_is_idempotent(self) -> None:
        manager = WatchlistManager()
        manager.create_watchlist("test", watchlist_type="manual")
        manager.add_asset("test", "BTC/USDT")
        manager.add_asset("test", "BTC/USDT")
        wl = manager.get_watchlist("test")
        assert len(wl.entries) == 1

    def test_remove_asset_from_watchlist(self) -> None:
        manager = WatchlistManager()
        manager.create_watchlist("test", watchlist_type="manual")
        manager.add_asset("test", "BTC/USDT")
        manager.add_asset("test", "ETH/USDT")
        manager.remove_asset("test", "BTC/USDT")
        wl = manager.get_watchlist("test")
        symbols = [e.symbol for e in wl.entries]
        assert "BTC/USDT" not in symbols
        assert "ETH/USDT" in symbols

    def test_update_from_rankings_auto_rebalance(self) -> None:
        manager = WatchlistManager()
        assets = [
            _make_ranked_asset("BTC/USDT", Tier.S, 1, composite=95.0),
            _make_ranked_asset("ETH/USDT", Tier.A, 2, composite=80.0),
            _make_ranked_asset("SOL/USDT", Tier.B, 3, composite=60.0),
            _make_ranked_asset("ADA/USDT", Tier.C, 4, composite=30.0),
        ]
        manager.update_from_rankings(assets)

        primary = manager.get_watchlist("primary")
        primary_symbols = {e.symbol for e in primary.entries}
        assert "BTC/USDT" in primary_symbols  # S-tier
        assert "ETH/USDT" in primary_symbols  # A-tier
        assert "SOL/USDT" not in primary_symbols  # B-tier

        secondary = manager.get_watchlist("secondary")
        secondary_symbols = {e.symbol for e in secondary.entries}
        assert "SOL/USDT" in secondary_symbols

    def test_monitoring_watchlist_tracks_promotions(self) -> None:
        manager = WatchlistManager()
        assets = [
            _make_ranked_asset("NEW/USDT", Tier.A, 2, promoted=True),
            _make_ranked_asset("OLD/USDT", Tier.S, 1, promoted=False),
        ]
        manager.update_from_rankings(assets)
        monitoring = manager.get_watchlist("monitoring")
        symbols = [e.symbol for e in monitoring.entries]
        assert "NEW/USDT" in symbols
        assert "OLD/USDT" not in symbols

    def test_manual_watchlist_not_auto_rebalanced(self) -> None:
        manager = WatchlistManager()
        manager.create_watchlist("manual_wl", watchlist_type="manual")
        manager.add_asset("manual_wl", "DOGE/USDT")

        assets = [
            _make_ranked_asset("BTC/USDT", Tier.S, 1),
        ]
        manager.update_from_rankings(assets)

        manual = manager.get_watchlist("manual_wl")
        assert len(manual.entries) == 1
        assert manual.entries[0].symbol == "DOGE/USDT"

    def test_event_published_on_create(self) -> None:
        mock_bus = MagicMock(spec=IEventBus)
        manager = WatchlistManager(event_bus=mock_bus)
        manager.create_watchlist("test_events")
        mock_bus.publish.assert_called()
