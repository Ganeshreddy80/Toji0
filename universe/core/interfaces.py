"""Abstract interfaces for all Universe Manager subsystems.

Every engine in the universe package implements one of these contracts.
"""

from __future__ import annotations

import abc
from typing import Any

from universe.core.models import (
    AssetRank,
    AssetScore,
    FilterResult,
    UniverseAsset,
    UniverseSnapshot,
    Watchlist,
)


class IDiscoveryProvider(abc.ABC):
    """Contract for exchange-specific asset discovery.

    Each provider wraps a Market Gateway provider to discover
    tradeable symbols and extract raw metadata.
    """

    @property
    @abc.abstractmethod
    def exchange_name(self) -> str:
        """Name of the exchange this provider discovers assets on."""

    @abc.abstractmethod
    def discover(self) -> list[UniverseAsset]:
        """Discover all tradeable assets on the exchange.

        Returns a list of partially-populated UniverseAsset objects
        with at least symbol, exchange, base_asset, and quote_asset set.
        """

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Check whether the underlying data source is reachable."""


class IMetadataEnricher(abc.ABC):
    """Contract for enriching raw discovered assets with metadata."""

    @abc.abstractmethod
    def enrich(self, assets: list[UniverseAsset]) -> list[UniverseAsset]:
        """Attach detailed metadata to each asset.

        Enrichment includes tick_size, lot_size, contract_type,
        fee_tier, asset_class, and any available launch date info.
        """


class IAssetFilter(abc.ABC):
    """Contract for filtering assets based on configurable rules."""

    @abc.abstractmethod
    def apply(self, assets: list[UniverseAsset]) -> tuple[list[UniverseAsset], list[FilterResult]]:
        """Run all filter rules against the asset list.

        Returns:
            A tuple of (passed_assets, all_filter_results).
            Filter results include reason strings for rejected assets.
        """


class IAssetScorer(abc.ABC):
    """Contract for computing multi-factor composite scores."""

    @abc.abstractmethod
    def score(self, assets: list[UniverseAsset]) -> list[UniverseAsset]:
        """Score each asset and attach an AssetScore to it.

        The composite score is a weighted sum of individual factor scores.
        """


class IAssetRanker(abc.ABC):
    """Contract for ranking scored assets into tiers."""

    @abc.abstractmethod
    def rank(
        self,
        assets: list[UniverseAsset],
        previous_ranks: dict[str, AssetRank] | None = None,
    ) -> list[UniverseAsset]:
        """Assign tier rankings and detect drift from previous scan.

        Args:
            assets: Scored asset list (must have scores attached).
            previous_ranks: Previous scan's rank map (symbol → AssetRank)
                           for drift detection.

        Returns:
            Assets with rank information attached.
        """


class IWatchlistManager(abc.ABC):
    """Contract for managing dynamic and manual watchlists."""

    @abc.abstractmethod
    def create_watchlist(self, name: str, watchlist_type: str = "auto") -> Watchlist:
        """Create a new named watchlist."""

    @abc.abstractmethod
    def get_watchlist(self, name: str) -> Watchlist | None:
        """Retrieve a watchlist by name."""

    @abc.abstractmethod
    def list_watchlists(self) -> list[Watchlist]:
        """List all watchlists."""

    @abc.abstractmethod
    def update_from_rankings(self, assets: list[UniverseAsset]) -> None:
        """Auto-rebalance auto-type watchlists from ranking results."""

    @abc.abstractmethod
    def add_asset(self, watchlist_name: str, symbol: str, reason: str = "") -> None:
        """Manually add an asset to a watchlist."""

    @abc.abstractmethod
    def remove_asset(self, watchlist_name: str, symbol: str) -> None:
        """Remove an asset from a watchlist."""


class IUniverseRepository(abc.ABC):
    """Contract for persisting universe state."""

    @abc.abstractmethod
    def save_snapshot(self, snapshot: UniverseSnapshot) -> None:
        """Persist a universe scan snapshot."""

    @abc.abstractmethod
    def load_latest_snapshot(self) -> UniverseSnapshot | None:
        """Load the most recent snapshot."""

    @abc.abstractmethod
    def load_snapshot_history(self, limit: int = 10) -> list[UniverseSnapshot]:
        """Load the last N snapshots for drift analysis."""
