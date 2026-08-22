"""Paper market orchestrator coordinating feed routing and pricing updates synchronization.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.paper_market.market_state_cache import MarketStateCache
from research_platform.paper_market.tick_dispatcher import TickDispatcher
from research_platform.paper_market.market_feed_router import MarketFeedRouter
from research_platform.paper_market.heartbeat_monitor import HeartbeatMonitor
from research_platform.paper_market.market_data_synchronizer import MarketDataSynchronizer
from research_platform.paper_market.paper_execution_router import PaperExecutionRouter
from research_platform.paper_market.repository import PaperMarketRepository

logger = logging.getLogger(__name__)


class PaperMarketOrchestrator:
    """Central manager coordinating real-time market data integration with paper trading engines."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = PaperMarketRepository()
        self._cache = MarketStateCache()
        self._dispatcher = TickDispatcher()
        self._heartbeat = HeartbeatMonitor(self._cache)
        self._synchronizer = MarketDataSynchronizer(container)
        
        self._feed_router = MarketFeedRouter(
            event_bus=self._event_bus,
            cache=self._cache,
            dispatcher=self._dispatcher
        )
        self._execution_router = PaperExecutionRouter(container=container)

    @property
    def cache(self) -> MarketStateCache:
        return self._cache

    @property
    def dispatcher(self) -> TickDispatcher:
        return self._dispatcher

    @property
    def feed_router(self) -> MarketFeedRouter:
        return self._feed_router

    @property
    def heartbeat(self) -> HeartbeatMonitor:
        return self._heartbeat

    @property
    def execution_router(self) -> PaperExecutionRouter:
        return self._execution_router

    # ── Downstream Integration Helpers ───────────────────────────────

    def _get_memory_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator"):
            return self._container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
        return None

    def _publish_memory_record(self, category: str, record: Any) -> None:
        mem_orch = self._get_memory_orchestrator()
        if not mem_orch:
            return
        try:
            mem_orch.publish_memory(category, record)
        except Exception as e:
            logger.error("Failed to publish to institutional memory: %s", e)

    # ── Orchestrator Actions ──────────────────────────────────────────

    def start_paper_market(self) -> None:
        """Initialize subscriptions routing and synchronize real-time updates."""
        # Register synchronizer listener callback
        self._dispatcher.register_listener(self._synchronizer.synchronize)
        
        # Start routing incoming ticks
        self._feed_router.start_routing()
        
        self._publish_memory_record("paper_market_logs", {"status": "STARTED", "msg": "Paper market data routing initialized."})
        logger.info("Paper Market Orchestrator: Market ticks routing started successfully ✓")

    def stop_paper_market(self) -> None:
        """Stop subscription feed routing."""
        self._feed_router.stop_routing()
        self._publish_memory_record("paper_market_logs", {"status": "STOPPED", "msg": "Paper market data routing stopped."})
        logger.info("Paper Market Orchestrator: Market ticks routing stopped ✓")
