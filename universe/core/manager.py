"""Central Universe Manager — the IPlugin orchestrator.

Coordinates the full scan pipeline:
  Discovery → Metadata → Filter → Score → Rank → Watchlist
Publishes UniverseUpdated events and manages the complete lifecycle.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from universe.core.events import (
    AssetDemoted,
    AssetDiscovered,
    AssetPromoted,
    UniverseUpdated,
)
from universe.core.models import (
    AssetRank,
    UniverseAsset,
    UniverseConfig,
    UniverseSnapshot,
)
from universe.discovery.engine import DiscoveryEngine
from universe.filters.engine import FilterEngine
from universe.health.monitor import UniverseHealthMonitor
from universe.metadata.engine import MetadataEngine
from universe.ranking.engine import RankingEngine
from universe.scoring.engine import ScoringEngine
from universe.storage.repository import UniverseRepository
from universe.watchlists.manager import WatchlistManager

logger = logging.getLogger(__name__)


class UniverseManager(IPlugin):
    """Institutional Asset Intelligence Layer.

    Decides which assets deserve analysis by running a full pipeline:
    1. Discovery: aggregate assets from multiple exchanges
    2. Metadata: enrich with tick/lot/fee/contract info
    3. Filter: apply quality gates (volume, price, quote)
    4. Score: compute multi-factor weighted scores
    5. Rank: assign S/A/B/C tiers with drift detection
    6. Watchlist: auto-rebalance named watchlists

    Publishes UniverseUpdated events for downstream consumers
    (e.g. the future Price Action Engine).
    """

    def __init__(
        self,
        event_bus: IEventBus,
        discovery_engine: DiscoveryEngine | None = None,
        metadata_engine: MetadataEngine | None = None,
        filter_engine: FilterEngine | None = None,
        scoring_engine: ScoringEngine | None = None,
        ranking_engine: RankingEngine | None = None,
        watchlist_manager: WatchlistManager | None = None,
        repository: UniverseRepository | None = None,
        health_monitor: UniverseHealthMonitor | None = None,
        config: UniverseConfig | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._config = config or UniverseConfig()
        self._state = ModuleState.CREATED

        # Sub-engines (injectable for testing)
        self._discovery = discovery_engine or DiscoveryEngine()
        self._metadata = metadata_engine or MetadataEngine()
        self._filter = filter_engine or FilterEngine(self._config)
        self._scoring = scoring_engine or ScoringEngine(self._config.scoring_weights)
        self._ranking = ranking_engine or RankingEngine(self._config.tier_boundaries)
        self._watchlists = watchlist_manager or WatchlistManager(event_bus)
        self._repository = repository or UniverseRepository(self._config)
        self._health = health_monitor or UniverseHealthMonitor()

        # State tracking
        self._previous_ranks: dict[str, AssetRank] = {}
        self._last_scan_result: list[UniverseAsset] = []

    # ── IPlugin Implementation ──────────────────────────────────────────

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("universe_manager")

    @property
    def name(self) -> str:
        return "Universe Manager"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list[PluginId]:
        return [PluginId("market_gateway")]

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Initialize the Universe Manager."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Universe Manager...")

        # Load previous scan state if available
        latest = self._repository.load_latest_snapshot()
        if latest:
            self._previous_ranks = {
                a.symbol: a.rank
                for a in latest.assets
                if a.rank
            }
            logger.info(
                "Loaded previous state: %d ranked assets", len(self._previous_ranks)
            )

        self._state = ModuleState.RUNNING
        logger.info("Universe Manager running successfully ✓")

    def shutdown(self) -> None:
        """Shut down the Universe Manager."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Universe Manager...")
        self._state = ModuleState.STOPPED
        logger.info("Universe Manager stopped successfully ✓")

    def health_check(self) -> HealthStatus:
        """Report universe health status."""
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY
        return self._health.health_check()

    # ── Scan Pipeline ───────────────────────────────────────────────────

    def run_scan(self) -> UniverseSnapshot:
        """Execute the full universe scan pipeline.

        Returns the completed UniverseSnapshot.
        """
        scan_id = f"scan_{uuid.uuid4().hex[:12]}"
        logger.info("Universe scan '%s' starting...", scan_id)

        # 1. Discovery
        discovered = self._discovery.discover_all()
        total_discovered = len(discovered)
        logger.info("Scan: Discovered %d raw assets", total_discovered)

        # Publish discovery events for new assets
        for asset in discovered:
            if asset.symbol not in self._previous_ranks:
                self._event_bus.publish(
                    AssetDiscovered(
                        source="universe.discovery",
                        payload={
                            "symbol": asset.symbol,
                            "exchanges": asset.exchanges,
                        },
                    )
                )

        # 2. Metadata Enrichment
        enriched = self._metadata.enrich(discovered)
        logger.info("Scan: Enriched %d assets with metadata", len(enriched))

        # 3. Filter
        filtered, filter_results = self._filter.apply(enriched)
        total_after_filter = len(filtered)
        logger.info(
            "Scan: %d/%d assets passed filters", total_after_filter, total_discovered
        )

        # 4. Score
        scored = self._scoring.score(filtered)
        logger.info("Scan: Scored %d assets", len(scored))

        # 5. Rank with drift detection
        ranked = self._ranking.rank(scored, self._previous_ranks)
        logger.info("Scan: Ranked %d assets", len(ranked))

        # Emit promotion/demotion events
        drift_count = 0
        for asset in ranked:
            if asset.rank and asset.rank.promoted:
                drift_count += 1
                self._event_bus.publish(
                    AssetPromoted(
                        source="universe.ranking",
                        payload={
                            "symbol": asset.symbol,
                            "from_tier": asset.rank.previous_tier.value if asset.rank.previous_tier else "UNRANKED",
                            "to_tier": asset.rank.tier.value,
                        },
                    )
                )
            elif asset.rank and asset.rank.demoted:
                drift_count += 1
                self._event_bus.publish(
                    AssetDemoted(
                        source="universe.ranking",
                        payload={
                            "symbol": asset.symbol,
                            "from_tier": asset.rank.previous_tier.value if asset.rank.previous_tier else "UNRANKED",
                            "to_tier": asset.rank.tier.value,
                        },
                    )
                )

        # 6. Update watchlists
        self._watchlists.update_from_rankings(ranked)
        logger.info("Scan: Watchlists updated")

        # Build tier distribution
        tier_distribution: dict[str, int] = {}
        for asset in ranked:
            if asset.rank:
                t = asset.rank.tier.value
                tier_distribution[t] = tier_distribution.get(t, 0) + 1

        # Build snapshot
        snapshot = UniverseSnapshot(
            scan_id=scan_id,
            scanned_at=datetime.now(UTC),
            total_discovered=total_discovered,
            total_after_filter=total_after_filter,
            assets=ranked,
            tier_distribution=tier_distribution,
            watchlists=self._watchlists.list_watchlists(),
            drift_count=drift_count,
        )

        # Persist
        self._repository.save_snapshot(snapshot)

        # Update health monitor
        self._health.update(snapshot)

        # Update previous ranks for next scan's drift detection
        self._previous_ranks = {
            a.symbol: a.rank
            for a in ranked
            if a.rank
        }
        self._last_scan_result = ranked

        # Publish UniverseUpdated event
        self._event_bus.publish(
            UniverseUpdated(
                source="universe.manager",
                payload={
                    "scan_id": scan_id,
                    "total_discovered": total_discovered,
                    "total_after_filter": total_after_filter,
                    "tier_distribution": tier_distribution,
                    "drift_count": drift_count,
                    "s_tier_symbols": [
                        a.symbol for a in ranked
                        if a.rank and a.rank.tier.value == "S"
                    ],
                    "a_tier_symbols": [
                        a.symbol for a in ranked
                        if a.rank and a.rank.tier.value == "A"
                    ],
                },
            )
        )

        logger.info(
            "Universe scan '%s' completed: discovered=%d filtered=%d "
            "tier_dist=%s drift=%d",
            scan_id,
            total_discovered,
            total_after_filter,
            tier_distribution,
            drift_count,
        )
        return snapshot

    # ── Accessors ───────────────────────────────────────────────────────

    @property
    def discovery_engine(self) -> DiscoveryEngine:
        """Access the discovery engine for provider registration."""
        return self._discovery

    @property
    def watchlist_manager(self) -> WatchlistManager:
        """Access the watchlist manager for manual operations."""
        return self._watchlists

    @property
    def health_monitor(self) -> UniverseHealthMonitor:
        """Access the health monitor for metrics."""
        return self._health

    @property
    def last_scan_result(self) -> list[UniverseAsset]:
        """Assets from the most recent scan."""
        return self._last_scan_result

    def get_detailed_health(self) -> dict[str, Any]:
        """Return detailed health metrics."""
        return self._health.get_metrics()
