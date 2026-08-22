"""Asset static specs and metadata lookup wrapper."""

from __future__ import annotations

from data.schemas.market_data import AssetMetadata
from toji_platform.core.types import AssetClass


class AssetMetadataLookup:
    """Registry wrapper for querying static properties of tradeable assets."""

    def __init__(self) -> None:
        self._assets: dict[str, AssetMetadata] = {}

    def add(self, asset: AssetMetadata) -> None:
        """Register asset metadata record."""
        self._assets[asset.symbol.upper()] = asset

    def get(self, symbol: str) -> AssetMetadata | None:
        """Retrieve registered metadata for symbol."""
        return self._assets.get(symbol.upper())

    def get_by_class(self, asset_class: AssetClass) -> list[AssetMetadata]:
        """List assets belonging to a specific asset class category."""
        return [meta for meta in self._assets.values() if meta.asset_class == asset_class]

    def count(self) -> int:
        """Total count of registered asset metadata records."""
        return len(self._assets)
