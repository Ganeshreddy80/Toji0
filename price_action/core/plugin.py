"""Price Action Subsystem Plugin implementation."""

from __future__ import annotations

import logging
from typing import Any

from market_intelligence.core.models import MarketState
from price_action.core.events import (
    PriceActionInitialized,
    PriceActionShutdown,
)
from price_action.core.exceptions import PriceActionException
from price_action.core.interfaces import IPatternRepository, IPatternStateStore
from price_action.core.models import PatternSnapshot
from price_action.core.repository import PriceActionRepository
from price_action.core.state import PriceActionStateStore
from price_action.analysis.pattern_engine import PatternEngine
from price_action.core.orchestrator import PriceActionOrchestrator
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId

logger = logging.getLogger(__name__)


class PriceActionPlugin(IPlugin):
    """Lifecycle controller and dependency injection binder for the Price Action Engine."""

    def __init__(
        self,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
        state_store: IPatternStateStore | None = None,
        repository: IPatternRepository | None = None,
        pattern_engine: PatternEngine | None = None,
        orchestrator: PriceActionOrchestrator | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container
        self._state_store = state_store
        self._repository = repository
        self._pattern_engine = pattern_engine
        self._orchestrator = orchestrator

        self._state = ModuleState.CREATED
        self._active_subscriptions: list[tuple[str, Any]] = []

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("price_action")

    @property
    def name(self) -> str:
        return "Price Action Engine"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list[PluginId]:
        # PAE depends on the Market Intelligence Layer
        return [PluginId("market_intelligence")]

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Initialize all subsystems and DI registrations."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Price Action Engine plugin...")

        # 1. Resolve container dependencies
        if self._container is not None:
            if self._event_bus is None and self._container.has(IEventBus):
                self._event_bus = self._container.resolve(IEventBus)
            if self._config_provider is None and self._container.has(IConfigProvider):
                self._config_provider = self._container.resolve(IConfigProvider)

        if self._event_bus is None:
            self._state = ModuleState.FAILED
            raise PriceActionException("Event Bus is required to initialize the Price Action plugin.")

        # 2. Setup state and repository
        history_limit = 1000
        if self._config_provider is not None:
            history_limit = self._config_provider.get("price_action.history_limit", 1000)

        if self._state_store is None:
            self._state_store = PriceActionStateStore(history_limit=history_limit)

        if self._repository is None:
            storage_engine = None
            if self._container is not None:
                for key in ["storage_engine", "postgres_storage", "data.storage.interfaces.IPostgresStorageEngine"]:
                    if self._container.has(key):
                        try:
                            storage_engine = self._container.resolve(key)
                            break
                        except Exception:
                            pass
            self._repository = PriceActionRepository(storage_engine=storage_engine)

        # 3. Setup PatternEngine & Orchestrator
        if self._pattern_engine is None:
            self._pattern_engine = PatternEngine(container=self._container)

        if self._orchestrator is None:
            self._orchestrator = PriceActionOrchestrator()

        self._orchestrator.initialize(
            pattern_engine=self._pattern_engine,
            state_store=self._state_store,
            repository=self._repository,
            event_bus=self._event_bus,
            container=self._container,
        )

        # 4. Register services in DI container
        if self._container is not None:
            if not self._container.has(IPatternStateStore):
                self._container.register(IPatternStateStore, instance=self._state_store)
            if not self._container.has(IPatternRepository):
                self._container.register(IPatternRepository, instance=self._repository)
            if not self._container.has(PatternEngine):
                self._container.register(PatternEngine, instance=self._pattern_engine)
            if not self._container.has(PriceActionOrchestrator):
                self._container.register(PriceActionOrchestrator, instance=self._orchestrator)
            if self._orchestrator.feature_store is not None and not self._container.has("price_action_feature_store"):
                self._container.register("price_action_feature_store", instance=self._orchestrator.feature_store)

        # 5. Subscribe to MIL events
        self._subscribe_event("system.market_state_updated", self._on_market_state_updated)
        self._subscribe_event("system.market_intelligence_completed", self._on_market_intelligence_completed)

        # 6. Publish initialization event
        init_event = PriceActionInitialized(
            source="price_action.plugin",
            payload={"version": self.version},
        )
        self._event_bus.publish(init_event)

        self._state = ModuleState.RUNNING
        logger.info("Price Action Engine plugin running successfully ✓")

    def shutdown(self) -> None:
        """Release plugin resources gracefully."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Price Action Engine plugin...")

        # 1. Unsubscribe event bus subscriptions
        if self._event_bus is not None:
            for event_type, handler in list(self._active_subscriptions):
                try:
                    self._event_bus.unsubscribe(event_type, handler)
                except Exception as e:
                    logger.error("Price Action: Failed to unsubscribe from %s: %s", event_type, e)
        self._active_subscriptions.clear()

        # 2. Publish shutdown event
        if self._event_bus is not None:
            try:
                shutdown_event = PriceActionShutdown(
                    source="price_action.plugin",
                    payload={"version": self.version},
                )
                self._event_bus.publish(shutdown_event)
            except Exception as e:
                logger.error("Price Action: Failed to publish PriceActionShutdown event: %s", e)

        # 3. Clear state store
        if self._state_store is not None:
            try:
                self._state_store.clear()
            except Exception as e:
                logger.error("Price Action: Error clearing state store: %s", e)

        self._state = ModuleState.STOPPED
        logger.info("Price Action Engine plugin stopped successfully ✓")

    def health_check(self) -> HealthStatus:
        """Return plugin status."""
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY

        if self._state_store is None or self._repository is None or self._orchestrator is None:
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def _subscribe_event(self, event_type: str, handler: Any) -> None:
        """Connect callback handler in the event bus."""
        self._event_bus.subscribe(event_type, handler)
        self._active_subscriptions.append((event_type, handler))

    def _on_market_state_updated(self, event: Any) -> None:
        """Process incoming analytical updates from the MIL."""
        logger.debug("Price Action: Received MarketStateUpdated event from %s", event.source)

        if not event or not hasattr(event, "payload") or not event.payload:
            return

        state_data = event.payload.get("state")
        if not state_data:
            return

        try:
            # Parse the serialized MarketState dict
            market_state = MarketState(**state_data)
            # Route to orchestrator
            if self._orchestrator is not None:
                self._orchestrator.process_market_state(market_state)
        except Exception as e:
            logger.error("Price Action: Failed to process MarketState update: %s", e)

    def _on_market_intelligence_completed(self, event: Any) -> None:
        """Process incoming completed updates from the MIL."""
        logger.debug("Price Action: Received MarketIntelligenceCompleted event from %s", event.source)
        if not event or not hasattr(event, "payload") or not event.payload:
            return
        state_data = event.payload.get("state")
        if not state_data:
            return
        try:
            from market_intelligence.core.models import MarketState
            market_state = MarketState(**state_data)
            if self._orchestrator is not None:
                self._orchestrator.process_market_state(market_state)
        except Exception as e:
            logger.error("Price Action: Failed to process MarketIntelligenceCompleted update: %s", e)

    @property
    def state_store(self) -> IPatternStateStore | None:
        return self._state_store

    @property
    def repository(self) -> IPatternRepository | None:
        return self._repository

    @property
    def pattern_engine(self) -> PatternEngine | None:
        return self._pattern_engine

    @property
    def orchestrator(self) -> PriceActionOrchestrator | None:
        return self._orchestrator
