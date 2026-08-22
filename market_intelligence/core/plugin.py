"""Market Intelligence Layer Plugin implementation."""

from __future__ import annotations

import logging
from typing import Any

from market_intelligence.core.analysis.engine import CoreAnalysisEngine
from market_intelligence.core.analysis.confidence import ConfidenceEngine
from market_intelligence.core.analysis.story import StoryGenerator
from market_intelligence.core.orchestrator import MarketIntelligenceOrchestrator
from market_intelligence.core.replay import ReplayVerifier
from market_intelligence.core.health import HealthMonitor
from market_intelligence.core.performance import PerformanceMonitor
from market_intelligence.core.events import (
    MILInitialized,
    MILShutdown,
)
from market_intelligence.core.exceptions import PluginInitializationError
from market_intelligence.core.interfaces import IRepository, IStateStore
from market_intelligence.core.models import MarketSnapshot
from market_intelligence.core.repository import MarketIntelligenceRepository
from market_intelligence.core.state import MarketIntelligenceState
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId

logger = logging.getLogger(__name__)


class MarketIntelligencePlugin(IPlugin):
    """Lifecycle controller and dependency injection binder for the MIL.

    Bootstraps state tracking and persistence repositories, hooks up event bus subscriptions,
    and runs health diagnostics.
    """

    def __init__(
        self,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
        state_store: IStateStore | None = None,
        repository: IRepository | None = None,
        engine: CoreAnalysisEngine | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container
        self._state_store = state_store
        self._repository = repository
        self._engine = engine
        self._orchestrator: MarketIntelligenceOrchestrator | None = None
        self._health_monitor: HealthMonitor | None = None
        self._performance_monitor: PerformanceMonitor | None = None
        self._replay_verifier: ReplayVerifier | None = None

        self._state = ModuleState.CREATED
        self._active_subscriptions: list[tuple[str, Any]] = []

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("market_intelligence")

    @property
    def name(self) -> str:
        return "Market Intelligence"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list[PluginId]:
        # MIL depends on the Universe Manager and Market Gateway
        return [PluginId("market_gateway"), PluginId("universe_manager")]

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Bootstrap the Market Intelligence Layer plugin and transition state to RUNNING."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Market Intelligence Layer plugin...")

        # 1. Resolve container dependencies
        if self._container is not None:
            if self._event_bus is None and self._container.has(IEventBus):
                self._event_bus = self._container.resolve(IEventBus)
            if self._config_provider is None and self._container.has(IConfigProvider):
                self._config_provider = self._container.resolve(IConfigProvider)

        if self._event_bus is None:
            self._state = ModuleState.FAILED
            raise PluginInitializationError(
                "Event Bus is required to initialize the Market Intelligence Layer plugin."
            )

        # 2. Load Configuration and Setup state/repository
        history_limit = 1000
        if self._config_provider is not None:
            history_limit = self._config_provider.get(
                "market_intelligence.history_limit", 1000
            )

        # 3. Instantiate core structures if not already injected
        if self._state_store is None:
            self._state_store = MarketIntelligenceState(history_limit=history_limit)

        if self._repository is None:
            storage_engine = None
            if self._container is not None:
                # Look for database or storage engine registrations in container
                for key in [
                    "data.storage.interfaces.IPostgresStorageEngine",
                    "postgres_storage",
                    "storage_engine",
                ]:
                    if self._container.has(key):
                        try:
                            storage_engine = self._container.resolve(key)
                            break
                        except Exception:
                            pass
            self._repository = MarketIntelligenceRepository(
                storage_engine=storage_engine
            )

        if self._engine is None:
            if self._container is not None and self._container.has(CoreAnalysisEngine):
                self._engine = self._container.resolve(CoreAnalysisEngine)
            else:
                pivot_strength = 2
                if self._config_provider is not None:
                    pivot_strength = self._config_provider.get(
                        "market_intelligence.pivot_strength", 2
                    )
                self._engine = CoreAnalysisEngine(
                    event_bus=self._event_bus, k=pivot_strength, state_store=self._state_store
                )

        # Initialize Sprint 5 Monitors, Verifiers, and Orchestrator
        self._health_monitor = HealthMonitor(self._event_bus)
        self._performance_monitor = PerformanceMonitor()
        self._replay_verifier = ReplayVerifier(self._event_bus)
        
        self._orchestrator = MarketIntelligenceOrchestrator(
            engine=self._engine,
            confidence_engine=self._engine.get_confidence_engine(),
            story_generator=self._engine.get_story_generator(),
            event_bus=self._event_bus,
            state_store=self._state_store,
            repository=self._repository,
            health_monitor=self._health_monitor,
            performance_monitor=self._performance_monitor,
        )

        # 4. Register services in container if container is available
        if self._container is not None:
            if not self._container.has(IStateStore):
                self._container.register(IStateStore, instance=self._state_store)
            if not self._container.has(IRepository):
                self._container.register(IRepository, instance=self._repository)
            if not self._container.has(CoreAnalysisEngine):
                self._container.register(CoreAnalysisEngine, instance=self._engine)
            from market_intelligence.core.interfaces import IMarketIntelligenceEngine
            if not self._container.has(IMarketIntelligenceEngine):
                self._container.register(IMarketIntelligenceEngine, instance=self._engine)
            
            from market_intelligence.core.analysis.volume import VolumeContextEngine
            from market_intelligence.core.analysis.liquidity import LiquidityEngine
            from market_intelligence.core.analysis.zone import ZoneEngine
            from market_intelligence.core.analysis.sr import SREngine
            from market_intelligence.core.analysis.session import SessionEngine
            from market_intelligence.core.analysis.mtf import MultiTimeframeEngine
            from market_intelligence.core.analysis.regime import MarketRegimeEngine
            from market_intelligence.core.analysis.correlation import CorrelationEngine
            from market_intelligence.core.analysis.context import MarketContextEngine

            if not self._container.has(VolumeContextEngine):
                self._container.register(VolumeContextEngine, instance=self._engine.get_volume_engine())
            if not self._container.has(LiquidityEngine):
                self._container.register(LiquidityEngine, instance=self._engine.get_liquidity_engine())
            if not self._container.has(ZoneEngine):
                self._container.register(ZoneEngine, instance=self._engine.get_zone_engine())
            if not self._container.has(SREngine):
                self._container.register(SREngine, instance=self._engine.get_sr_engine())
            if not self._container.has(SessionEngine):
                self._container.register(SessionEngine, instance=self._engine.get_session_engine())
            if not self._container.has(MultiTimeframeEngine):
                self._container.register(MultiTimeframeEngine, instance=self._engine.get_mtf_engine())
            if not self._container.has(MarketRegimeEngine):
                self._container.register(MarketRegimeEngine, instance=self._engine.get_regime_engine())
            if not self._container.has(CorrelationEngine):
                self._container.register(CorrelationEngine, instance=self._engine.get_correlation_engine())
            if not self._container.has(MarketContextEngine):
                self._container.register(MarketContextEngine, instance=self._engine.get_context_engine())

            # Register Sprint 5 elements in container
            if not self._container.has(HealthMonitor):
                self._container.register(HealthMonitor, instance=self._health_monitor)
            if not self._container.has(PerformanceMonitor):
                self._container.register(PerformanceMonitor, instance=self._performance_monitor)
            if not self._container.has(ReplayVerifier):
                self._container.register(ReplayVerifier, instance=self._replay_verifier)
            if not self._container.has(MarketIntelligenceOrchestrator):
                self._container.register(MarketIntelligenceOrchestrator, instance=self._orchestrator)
            if not self._container.has(ConfidenceEngine):
                self._container.register(ConfidenceEngine, instance=self._engine.get_confidence_engine())
            if not self._container.has(StoryGenerator):
                self._container.register(StoryGenerator, instance=self._engine.get_story_generator())

        # 5. Connect event subscriptions
        self._subscribe_event("system.market_data_updated", self._on_market_data_updated)
        self._subscribe_event("system.market_data_received", self._on_market_data_received)
        self._subscribe_event("system.universe_updated", self._on_universe_updated)

        # 6. Publish initialization success event
        init_event = MILInitialized(
            source="market_intelligence.plugin",
            payload={"version": self.version},
        )
        self._event_bus.publish(init_event)

        self._state = ModuleState.RUNNING
        logger.info("Market Intelligence Layer plugin running successfully ✓")

    def shutdown(self) -> None:
        """Gracefully release resources and transition state to STOPPED."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Market Intelligence Layer plugin...")

        # 1. Unsubscribe event bus subscriptions
        if self._event_bus is not None:
            for event_type, handler in list(self._active_subscriptions):
                try:
                    self._event_bus.unsubscribe(event_type, handler)
                except Exception as e:
                    logger.error(
                        "Failed to unsubscribe from %s: %s", event_type, e
                    )
        self._active_subscriptions.clear()

        # 2. Publish shutdown event
        if self._event_bus is not None:
            try:
                shutdown_event = MILShutdown(
                    source="market_intelligence.plugin",
                    payload={"version": self.version},
                )
                self._event_bus.publish(shutdown_event)
            except Exception as e:
                logger.error("Failed to publish MILShutdown event: %s", e)

        # 3. Clear in-memory state store
        if self._state_store is not None:
            try:
                self._state_store.clear()
            except Exception as e:
                logger.error("Error clearing state store during shutdown: %s", e)

        self._state = ModuleState.STOPPED
        logger.info("Market Intelligence Layer plugin stopped successfully ✓")

    def health_check(self) -> HealthStatus:
        """Diagnose MIL plugin health status."""
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY

        if self._orchestrator is None:
            return HealthStatus.UNHEALTHY

        report = self._orchestrator.get_health()
        from market_intelligence.core.enums import HealthState
        if report.overall_status == HealthState.HEALTHY:
            return HealthStatus.HEALTHY
        elif report.overall_status == HealthState.DEGRADED:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNHEALTHY

    def _subscribe_event(self, event_type: str, handler: Any) -> None:
        """Register subscriber handler in the event bus."""
        self._event_bus.subscribe(event_type, handler)
        self._active_subscriptions.append((event_type, handler))

    def _on_market_data_updated(self, event: Any) -> None:
        """Callback triggered on new market data ingestion."""
        logger.debug("MIL: Received MarketDataUpdated event from %s", event.source)
        
        # 1. Parse candle
        if not hasattr(event, "candle"):
            return
            
        candle = event.candle

        if self._orchestrator is None:
            logger.warning("MIL: Orchestrator not initialized.")
            return

        # Let the orchestrator handle processing
        self._orchestrator.process_candle(candle)

    def _on_market_data_received(self, event: Any) -> None:
        """Callback triggered on new market data received from gateway."""
        logger.debug("MIL: Received MarketDataReceived event from %s", event.source)
        if not event or not hasattr(event, "payload") or not event.payload:
            return
        candle_data = event.payload.get("candle")
        if not candle_data:
            return
        try:
            from data.schemas.market_data import OHLCV
            candle = OHLCV(**candle_data)
            if self._orchestrator is not None:
                self._orchestrator.process_candle(candle)
        except Exception as e:
            logger.error("MIL: Failed to process MarketDataReceived event: %s", e)

    def _on_universe_updated(self, event: Any) -> None:
        """Callback triggered on universe scan rebalances."""
        logger.debug("MIL: Received UniverseUpdated event from %s", event.source)

    @property
    def state_store(self) -> IStateStore | None:
        """Retrieve the in-memory state store."""
        return self._state_store

    @property
    def repository(self) -> IRepository | None:
        """Retrieve the persistence repository."""
        return self._repository

    @property
    def engine(self) -> CoreAnalysisEngine | None:
        """Retrieve the coordinated core analysis engine."""
        return self._engine

    @property
    def orchestrator(self) -> MarketIntelligenceOrchestrator | None:
        """Retrieve the system orchestrator."""
        return self._orchestrator

    @property
    def health_monitor(self) -> HealthMonitor | None:
        """Retrieve the system health monitor."""
        return self._health_monitor

    @property
    def performance_monitor(self) -> PerformanceMonitor | None:
        """Retrieve the system performance monitor."""
        return self._performance_monitor

    @property
    def replay_verifier(self) -> ReplayVerifier | None:
        """Retrieve the system replay verifier."""
        return self._replay_verifier
