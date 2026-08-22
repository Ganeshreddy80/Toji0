"""Unit tests for the Universe Manager."""

from __future__ import annotations

import pytest
from data.schemas.market_data import AssetMetadata
from toji_platform.core.types import AssetClass
from intelligence.universe.manager import UniverseManager


@pytest.fixture
def manager() -> UniverseManager:
    """Provide a fresh UniverseManager instance."""
    return UniverseManager()


@pytest.fixture
def sample_asset() -> AssetMetadata:
    """Provide a mock AssetMetadata for testing."""
    return AssetMetadata(
        symbol="BTC/USDT",
        asset_class=AssetClass.CRYPTO,
        base_asset="BTC",
        quote_asset="USDT",
        tick_size=0.01,
        lot_size=0.0001,
        exchange="Binance",
    )


def test_asset_registration(manager: UniverseManager, sample_asset: AssetMetadata) -> None:
    """Test registering and retrieving an asset."""
    manager.register_asset(
        asset=sample_asset,
        sector="L1",
        market_group="Majors",
        custom_attributes={"is_active": True},
    )

    retrieved = manager.get_asset("BTC/USDT")
    assert retrieved is not None
    assert retrieved.symbol == "BTC/USDT"
    assert retrieved.exchange == "Binance"

    info = manager.get_asset_info("BTC/USDT")
    assert info is not None
    assert info.sector == "L1"
    assert info.market_group == "Majors"
    assert info.custom_attributes["is_active"] is True


def test_watchlist_management(manager: UniverseManager, sample_asset: AssetMetadata) -> None:
    """Test watchlist CRUD actions."""
    manager.register_asset(sample_asset)
    # Register another asset
    asset2 = AssetMetadata(
        symbol="ETH/USDT",
        asset_class=AssetClass.CRYPTO,
        base_asset="ETH",
        quote_asset="USDT",
        exchange="Binance",
    )
    manager.register_asset(asset2)

    manager.create_watchlist("TradingList", ["BTC/USDT", "ETH/USDT", "INVALID"])
    watchlist = manager.get_watchlist("TradingList")

    assert len(watchlist) == 2
    assert "BTC/USDT" in watchlist
    assert "ETH/USDT" in watchlist
    assert "INVALID" not in watchlist

    manager.remove_from_watchlist("TradingList", "ETH/USDT")
    assert "ETH/USDT" not in manager.get_watchlist("TradingList")

    manager.add_to_watchlist("TradingList", "ETH/USDT")
    assert "ETH/USDT" in manager.get_watchlist("TradingList")


def test_group_filtering(manager: UniverseManager, sample_asset: AssetMetadata) -> None:
    """Test listing assets by category, exchange, and group filters."""
    manager.register_asset(sample_asset, sector="L1", market_group="Majors")

    stock_asset = AssetMetadata(
        symbol="AAPL",
        asset_class=AssetClass.STOCKS,
        base_asset="AAPL",
        quote_asset="USD",
        exchange="NASDAQ",
    )
    manager.register_asset(stock_asset, sector="Tech", market_group="US Equities")

    assert len(manager.get_assets_by_sector("L1")) == 1
    assert len(manager.get_assets_by_exchange("Binance")) == 1
    assert len(manager.get_assets_by_class(AssetClass.STOCKS)) == 1
    assert len(manager.get_assets_by_market_group("Majors")) == 1

    # Check case insensitivity
    assert len(manager.get_assets_by_sector("l1")) == 1


def test_dynamic_filtering(manager: UniverseManager, sample_asset: AssetMetadata) -> None:
    """Test dynamic query-based filtering."""
    manager.register_asset(sample_asset, sector="L1", market_group="Majors", custom_attributes={"high_vol": True})

    stock_asset = AssetMetadata(
        symbol="AAPL",
        asset_class=AssetClass.STOCKS,
        base_asset="AAPL",
        quote_asset="USD",
        exchange="NASDAQ",
    )
    manager.register_asset(stock_asset, sector="Tech", market_group="US Equities", custom_attributes={"high_vol": False})

    # Test basic attribute filtering
    res = manager.filter_assets({"exchange": "NASDAQ"})
    assert len(res) == 1
    assert res[0].symbol == "AAPL"

    # Test sector
    res = manager.filter_assets({"sector": "L1"})
    assert len(res) == 1

    # Test custom attributes
    res = manager.filter_assets({"high_vol": True})
    assert len(res) == 1
    assert res[0].symbol == "BTC/USDT"

    # Multiple matching criteria
    res = manager.filter_assets({"asset_class": AssetClass.CRYPTO, "sector": "L1", "high_vol": True})
    assert len(res) == 1
