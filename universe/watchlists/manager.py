"""Dynamic and manual watchlist management.

Manages named watchlists that are auto-rebalanced from ranking results
or manually curated by the user. Publishes WatchlistUpdated events.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from toji_platform.core.event_bus.interfaces import IEventBus
from universe.core.events import WatchlistUpdated
from universe.core.interfaces import IWatchlistManager
from universe.core.models import (
    Tier,
    UniverseAsset,
    Watchlist,
    WatchlistEntry,
    WatchlistType,
)

logger = logging.getLogger(__name__)


# Default auto-watchlist definitions
_DEFAULT_AUTO_WATCHLISTS: dict[str, dict[str, list[Tier] | str]] = {
    "primary": {
        "tiers": [Tier.S, Tier.A],
        "description": "S-Tier + A-Tier: highest conviction assets",
    },
    "secondary": {
        "tiers": [Tier.B],
        "description": "B-Tier: moderate conviction assets",
    },
    "monitoring": {
        "tiers": [Tier.S, Tier.A],
        "description": "Recently promoted assets under observation",
    },
}


class WatchlistManager(IWatchlistManager):
    """Manage named, dynamic watchlists driven by ranking results.

    Auto-type watchlists are rebalanced on every scan.
    Manual-type watchlists are user-controlled and never auto-modified.
    """

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus
        self._watchlists: dict[str, Watchlist] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Create default auto-watchlists."""
        for name, config in _DEFAULT_AUTO_WATCHLISTS.items():
            self._watchlists[name] = Watchlist(
                name=name,
                watchlist_type=WatchlistType.AUTO,
                description=str(config.get("description", "")),
            )

    def create_watchlist(
        self, name: str, watchlist_type: str = "auto"
    ) -> Watchlist:
        """Create a new named watchlist."""
        wl_type = WatchlistType(watchlist_type)
        watchlist = Watchlist(
            name=name,
            watchlist_type=wl_type,
            last_updated=datetime.now(UTC),
        )
        self._watchlists[name] = watchlist
        logger.info("Watchlist: Created '%s' (type=%s)", name, watchlist_type)
        self._publish_update(name, "created")
        return watchlist

    def get_watchlist(self, name: str) -> Watchlist | None:
        """Retrieve a watchlist by name."""
        return self._watchlists.get(name)

    def list_watchlists(self) -> list[Watchlist]:
        """List all watchlists."""
        return list(self._watchlists.values())

    def update_from_rankings(self, assets: list[UniverseAsset]) -> None:
        """Auto-rebalance auto-type watchlists from ranking results.

        Only modifies watchlists with type=AUTO. Manual watchlists are untouched.
        """
        now = datetime.now(UTC)

        for name, watchlist in self._watchlists.items():
            if watchlist.watchlist_type != WatchlistType.AUTO:
                continue

            config = _DEFAULT_AUTO_WATCHLISTS.get(name)
            if not config:
                continue

            target_tiers: list[Tier] = config.get("tiers", [])  # type: ignore[assignment]

            if name == "monitoring":
                # Monitoring: only recently promoted assets
                entries = self._build_monitoring_entries(assets, now)
            else:
                # Standard tier-based rebalance
                entries = self._build_tier_entries(assets, target_tiers, now)

            watchlist.entries = entries
            watchlist.last_updated = now

        logger.info(
            "Watchlist: Auto-rebalanced %d watchlists",
            sum(
                1
                for w in self._watchlists.values()
                if w.watchlist_type == WatchlistType.AUTO
            ),
        )

    def add_asset(
        self, watchlist_name: str, symbol: str, reason: str = ""
    ) -> None:
        """Manually add an asset to a watchlist."""
        watchlist = self._watchlists.get(watchlist_name)
        if not watchlist:
            raise ValueError(f"Watchlist '{watchlist_name}' not found")

        # Don't add duplicates
        if any(e.symbol == symbol for e in watchlist.entries):
            return

        entry = WatchlistEntry(
            symbol=symbol,
            reason=reason or "Manually added",
            added_at=datetime.now(UTC),
        )
        watchlist.entries.append(entry)
        watchlist.last_updated = datetime.now(UTC)
        logger.info("Watchlist: Added '%s' to '%s'", symbol, watchlist_name)
        self._publish_update(watchlist_name, "asset_added")

    def remove_asset(self, watchlist_name: str, symbol: str) -> None:
        """Remove an asset from a watchlist."""
        watchlist = self._watchlists.get(watchlist_name)
        if not watchlist:
            raise ValueError(f"Watchlist '{watchlist_name}' not found")

        watchlist.entries = [
            e for e in watchlist.entries if e.symbol != symbol
        ]
        watchlist.last_updated = datetime.now(UTC)
        logger.info(
            "Watchlist: Removed '%s' from '%s'", symbol, watchlist_name
        )
        self._publish_update(watchlist_name, "asset_removed")

    def _build_tier_entries(
        self,
        assets: list[UniverseAsset],
        target_tiers: list[Tier],
        now: datetime,
    ) -> list[WatchlistEntry]:
        """Build watchlist entries from assets in target tiers."""
        entries: list[WatchlistEntry] = []
        for asset in assets:
            if asset.rank and asset.rank.tier in target_tiers:
                entries.append(
                    WatchlistEntry(
                        symbol=asset.symbol,
                        reason=f"Tier {asset.rank.tier.value} — rank #{asset.rank.position}",
                        added_at=now,
                        composite_score=(
                            asset.score.composite_score if asset.score else 0.0
                        ),
                        tier=asset.rank.tier,
                    )
                )
        return entries

    def _build_monitoring_entries(
        self, assets: list[UniverseAsset], now: datetime
    ) -> list[WatchlistEntry]:
        """Build monitoring watchlist from recently promoted assets."""
        entries: list[WatchlistEntry] = []
        for asset in assets:
            if asset.rank and asset.rank.promoted:
                entries.append(
                    WatchlistEntry(
                        symbol=asset.symbol,
                        reason=f"Promoted from {asset.rank.previous_tier.value if asset.rank.previous_tier else 'UNRANKED'} to {asset.rank.tier.value}",
                        added_at=now,
                        composite_score=(
                            asset.score.composite_score if asset.score else 0.0
                        ),
                        tier=asset.rank.tier,
                    )
                )
        return entries

    def _publish_update(self, watchlist_name: str, action: str) -> None:
        """Publish a WatchlistUpdated event if event bus is available."""
        if not self._event_bus:
            return
        event = WatchlistUpdated(
            source="universe.watchlists",
            payload={
                "watchlist_name": watchlist_name,
                "action": action,
            },
        )
        self._event_bus.publish(event)
