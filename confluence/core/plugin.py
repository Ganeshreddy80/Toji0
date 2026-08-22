"""Confluence Subsystem Plugin implementation."""

from __future__ import annotations

import logging
from typing import Any

from confluence.core.events import (
    ConfluenceInitialized,
    ConfluenceShutdown,
)
from confluence.core.exceptions import ConfluenceException
from confluence.core.interfaces import (
    IConfluenceEngine,
    IConfluenceRepository,
    IConfluenceStateStore,
)
from confluence.core.models import ConfluenceSnapshot
from confluence.core.repository import ConfluenceRepository
from confluence.core.state import ConfluenceStateStore
from confluence.core.orchestrator import ConfluenceOrchestrator
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId

logger = logging.getLogger(__name__)


class ConfluencePlugin(IPlugin):
    """Lifecycle controller and dependency injection binder for the Confluence Engine."""

    def __init__(
        self,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
        state_store: IConfluenceStateStore | None = None,
        repository: IConfluenceRepository | None = None,
        confluence_engine: IConfluenceEngine | None = None,
        orchestrator: ConfluenceOrchestrator | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container
        self._state_store = state_store
        self._repository = repository
        self._confluence_engine = confluence_engine
        self._orchestrator = orchestrator

        self._state = ModuleState.CREATED
        self._active_subscriptions: list[tuple[str, Any]] = []

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("confluence")

    @property
    def name(self) -> str:
        return "Confluence Engine"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list[PluginId]:
        return [PluginId("market_intelligence"), PluginId("price_action")]

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Initialize all subsystems and DI registrations."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Confluence Engine plugin...")

        # 1. Resolve container dependencies
        if self._container is not None:
            if self._event_bus is None and self._container.has(IEventBus):
                self._event_bus = self._container.resolve(IEventBus)
            if self._config_provider is None and self._container.has(IConfigProvider):
                self._config_provider = self._container.resolve(IConfigProvider)

        if self._event_bus is None:
            self._state = ModuleState.FAILED
            raise ConfluenceException(
                "Event Bus is required to initialize the Confluence plugin."
            )

        # 2. Setup state and repository
        history_limit = 1000
        if self._config_provider is not None:
            history_limit = self._config_provider.get(
                "confluence.history_limit", 1000
            )

        if self._state_store is None:
            self._state_store = ConfluenceStateStore(history_limit=history_limit)

        if self._repository is None:
            storage_engine = None
            if self._container is not None:
                for key in [
                    "storage_engine",
                    "postgres_storage",
                    "data.storage.interfaces.IPostgresStorageEngine",
                ]:
                    if self._container.has(key):
                        try:
                            storage_engine = self._container.resolve(key)
                            break
                        except Exception:
                            pass
            self._repository = ConfluenceRepository(storage_engine=storage_engine)

        # 3. Setup ConfluenceEngine & Orchestrator
        if self._confluence_engine is None:
            from confluence.analysis.confluence_engine import ConfluenceEngine
            self._confluence_engine = ConfluenceEngine(container=self._container)

        if self._orchestrator is None:
            self._orchestrator = ConfluenceOrchestrator()

        self._orchestrator.initialize(
            confluence_engine=self._confluence_engine,
            state_store=self._state_store,
            repository=self._repository,
            event_bus=self._event_bus,
            container=self._container,
        )

        # 4. Register services in DI container
        if self._container is not None:
            if not self._container.has(IConfluenceStateStore):
                self._container.register(
                    IConfluenceStateStore, instance=self._state_store
                )
            if not self._container.has(IConfluenceRepository):
                self._container.register(
                    IConfluenceRepository, instance=self._repository
                )
            if not self._container.has(IConfluenceEngine):
                self._container.register(
                    IConfluenceEngine, instance=self._confluence_engine
                )
            if not self._container.has(ConfluenceOrchestrator):
                self._container.register(
                    ConfluenceOrchestrator, instance=self._orchestrator
                )

        # 5. Subscribe to events
        self._subscribe_event(
            "system.market_state_updated", self._on_market_state_updated
        )
        self._subscribe_event(
            "system.pattern_updated", self._on_pattern_updated
        )
        self._subscribe_event(
            "system.pattern_quality_updated", self._on_pattern_quality_updated
        )
        self._subscribe_event(
            "system.price_action_completed", self._on_price_action_completed
        )

        # 6. Publish initialization event
        init_event = ConfluenceInitialized(
            source="confluence.plugin",
            payload={"version": self.version},
        )
        self._event_bus.publish(init_event)

        self._state = ModuleState.RUNNING
        logger.info("Confluence Engine plugin running successfully ✓")

    def shutdown(self) -> None:
        """Release plugin resources gracefully."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Confluence Engine plugin...")

        # 1. Unsubscribe event bus subscriptions
        if self._event_bus is not None:
            for event_type, handler in list(self._active_subscriptions):
                try:
                    self._event_bus.unsubscribe(event_type, handler)
                except Exception as e:
                    logger.error(
                        "Confluence: Failed to unsubscribe from %s: %s",
                        event_type,
                        e,
                    )
        self._active_subscriptions.clear()

        # 2. Publish shutdown event
        if self._event_bus is not None:
            try:
                shutdown_event = ConfluenceShutdown(
                    source="confluence.plugin",
                    payload={"version": self.version},
                )
                self._event_bus.publish(shutdown_event)
            except Exception as e:
                logger.error(
                    "Confluence: Failed to publish ConfluenceShutdown event: %s",
                    e,
                )

        # 3. Clear state store
        if self._state_store is not None:
            try:
                self._state_store.clear()
            except Exception as e:
                logger.error("Confluence: Error clearing state store: %s", e)

        self._state = ModuleState.STOPPED
        logger.info("Confluence Engine plugin stopped successfully ✓")

    def health_check(self) -> HealthStatus:
        """Return plugin status."""
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY

        if (
            self._state_store is None
            or self._repository is None
            or self._orchestrator is None
        ):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def _subscribe_event(self, event_type: str, handler: Any) -> None:
        """Connect callback handler in the event bus."""
        self._event_bus.subscribe(event_type, handler)
        self._active_subscriptions.append((event_type, handler))

    def _on_market_state_updated(self, event: Any) -> None:
        """Process incoming analytical updates from the MIL."""
        logger.debug(
            "Confluence: Received MarketStateUpdated event from %s", event.source
        )
        self._process_event_state(event)

    def _on_pattern_updated(self, event: Any) -> None:
        """Process incoming pattern updates from PAE."""
        logger.debug(
            "Confluence: Received PatternUpdated event from %s", event.source
        )
        self._process_event_state(event)

    def _on_price_action_completed(self, event: Any) -> None:
        """Process incoming price action completed updates from PAE."""
        logger.debug(
            "Confluence: Received PriceActionCompleted event from %s", event.source
        )
        self._process_event_state(event)

    def _on_pattern_quality_updated(self, event: Any) -> None:
        """Process incoming pattern quality updates from PQE."""
        logger.debug(
            "Confluence: Received PatternQualityUpdated event from %s",
            event.source,
        )
        self._process_event_state(event)

    def _process_event_state(self, event: Any) -> None:
        if not event or not hasattr(event, "payload") or not event.payload:
            return

        symbol = event.payload.get("symbol")
        timeframe = event.payload.get("timeframe")

        if not (symbol and timeframe):
            # Try to fall back to nested state/pattern/quality fields
            for key in ("state", "pattern", "quality", "candidate", "match"):
                nested = event.payload.get(key)
                if nested and isinstance(nested, dict):
                    symbol = symbol or nested.get("symbol")
                    timeframe = timeframe or nested.get("timeframe")

        if not (symbol and timeframe):
            return

        try:
            if self._orchestrator is not None:
                self._orchestrator.process_confluence(symbol, timeframe)
        except Exception as e:
            logger.error(
                "Confluence: Failed to process event update for %s %s: %s",
                symbol,
                timeframe,
                e,
            )

    @property
    def state_store(self) -> IConfluenceStateStore | None:
        return self._state_store

    @property
    def repository(self) -> IConfluenceRepository | None:
        return self._repository

    @property
    def confluence_engine(self) -> IConfluenceEngine | None:
        return self._confluence_engine

    @property
    def orchestrator(self) -> ConfluenceOrchestrator | None:
        return self._orchestrator
