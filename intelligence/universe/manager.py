"""Universe Manager for registering assets, watchlists, groups, and dynamic filtering."""

from __future__ import annotations

import enum
from typing import Any
from pydantic import BaseModel, Field
from data.schemas.market_data import AssetMetadata
from toji_platform.core.types import AssetClass


class AssetUniverseInfo(BaseModel):
    """Internal schema for asset registry info within a universe."""

    metadata: AssetMetadata
    sector: str = Field(default="unknown", description="Sector classification (e.g. DeFi, Layer1, Tech)")
    market_group: str = Field(default="unknown", description="Market group classification (e.g. Major, Minor)")
    custom_attributes: dict[str, Any] = Field(default_factory=dict, description="Arbitrary custom properties")


class UniverseManager:
    """Manages multi-asset registration, watchlists, classification groups, and dynamic filters."""

    def __init__(self) -> None:
        """Initialize the UniverseManager."""
        self._assets: dict[str, AssetUniverseInfo] = {}
        self._watchlists: dict[str, set[str]] = {}

    def register_asset(
        self,
        asset: AssetMetadata,
        sector: str | None = None,
        market_group: str | None = None,
        custom_attributes: dict[str, Any] | None = None,
    ) -> None:
        """Register an asset with metadata and classification groups.

        Args:
            asset: Canonical AssetMetadata object.
            sector: Optional sector classification string.
            market_group: Optional market group string.
            custom_attributes: Optional custom dictionary of parameters.
        """
        self._assets[asset.symbol] = AssetUniverseInfo(
            metadata=asset,
            sector=sector or "unknown",
            market_group=market_group or "unknown",
            custom_attributes=custom_attributes or {},
        )

    def get_asset(self, symbol: str) -> AssetMetadata | None:
        """Retrieve the metadata for a registered asset.

        Args:
            symbol: Ticker symbol.

        Returns:
            AssetMetadata if registered, else None.
        """
        info = self._assets.get(symbol)
        return info.metadata if info else None

    def get_asset_info(self, symbol: str) -> AssetUniverseInfo | None:
        """Retrieve full universe info for an asset, including sector and groups.

        Args:
            symbol: Ticker symbol.

        Returns:
            AssetUniverseInfo if registered, else None.
        """
        return self._assets.get(symbol)

    def deregister_asset(self, symbol: str) -> None:
        """Remove an asset from the universe.

        Args:
            symbol: Ticker symbol.
        """
        self._assets.pop(symbol, None)
        for watchlist in self._watchlists.values():
            watchlist.discard(symbol)

    def create_watchlist(self, name: str, symbols: list[str]) -> None:
        """Create or update a watchlist.

        Args:
            name: Watchlist name.
            symbols: List of symbols in the watchlist.
        """
        self._watchlists[name] = {sym for sym in symbols if sym in self._assets}

    def get_watchlist(self, name: str) -> list[str]:
        """Get symbols in a watchlist.

        Args:
            name: Watchlist name.

        Returns:
            List of registered symbols in the watchlist.
        """
        return sorted(list(self._watchlists.get(name, set())))

    def add_to_watchlist(self, name: str, symbol: str) -> None:
        """Add a single symbol to a watchlist if registered.

        Args:
            name: Watchlist name.
            symbol: Ticker symbol.
        """
        if symbol in self._assets:
            if name not in self._watchlists:
                self._watchlists[name] = set()
            self._watchlists[name].add(symbol)

    def remove_from_watchlist(self, name: str, symbol: str) -> None:
        """Remove a single symbol from a watchlist.

        Args:
            name: Watchlist name.
            symbol: Ticker symbol.
        """
        if name in self._watchlists:
            self._watchlists[name].discard(symbol)

    def get_assets_by_sector(self, sector: str) -> list[AssetMetadata]:
        """Get all registered assets belonging to a specific sector.

        Args:
            sector: Sector classification.

        Returns:
            List of matching AssetMetadata.
        """
        return [
            info.metadata
            for info in self._assets.values()
            if info.sector.lower() == sector.lower()
        ]

    def get_assets_by_exchange(self, exchange: str) -> list[AssetMetadata]:
        """Get all registered assets belonging to a specific exchange.

        Args:
            exchange: Exchange name.

        Returns:
            List of matching AssetMetadata.
        """
        return [
            info.metadata
            for info in self._assets.values()
            if info.metadata.exchange and info.metadata.exchange.lower() == exchange.lower()
        ]

    def get_assets_by_class(self, asset_class: AssetClass) -> list[AssetMetadata]:
        """Get all registered assets matching an asset class.

        Args:
            asset_class: AssetClass enum.

        Returns:
            List of matching AssetMetadata.
        """
        return [
            info.metadata
            for info in self._assets.values()
            if info.metadata.asset_class == asset_class
        ]

    def get_assets_by_market_group(self, market_group: str) -> list[AssetMetadata]:
        """Get all registered assets belonging to a specific market group.

        Args:
            market_group: Market group classification.

        Returns:
            List of matching AssetMetadata.
        """
        return [
            info.metadata
            for info in self._assets.values()
            if info.market_group.lower() == market_group.lower()
        ]

    def get_all_assets(self) -> list[AssetMetadata]:
        """Get all registered assets.

        Returns:
            List of all AssetMetadata.
        """
        return [info.metadata for info in self._assets.values()]

    def filter_assets(self, criteria: dict[str, Any]) -> list[AssetMetadata]:
        """Dynamically filter assets based on custom criteria values matching metadata or universe info.

        Supported criteria fields can match metadata properties, sector, market_group,
        or keys inside custom_attributes.

        Args:
            criteria: Dictionary of key-value constraints.

        Returns:
            List of matching AssetMetadata.
        """
        results = []
        for info in self._assets.values():
            match = True
            for key, val in criteria.items():
                # Check metadata attributes first
                if hasattr(info.metadata, key):
                    attr_val = getattr(info.metadata, key)
                    if isinstance(attr_val, enum.Enum):
                        attr_val = attr_val.value
                    if isinstance(val, enum.Enum):
                        val = val.value
                    if attr_val != val:
                        match = False
                        break
                # Check sector, market group
                elif key == "sector":
                    if info.sector.lower() != str(val).lower():
                        match = False
                        break
                elif key == "market_group":
                    if info.market_group.lower() != str(val).lower():
                        match = False
                        break
                # Check custom attributes
                elif key in info.custom_attributes:
                    if info.custom_attributes[key] != val:
                        match = False
                        break
                else:
                    match = False
                    break
            if match:
                results.append(info.metadata)
        return results
