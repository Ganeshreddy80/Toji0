"""Trading Context Subsystem Plugin implementation."""

from __future__ import annotations

import logging
from typing import Any

from trading_context.core.events import (
    TradingContextInitialized,
    TradingContextShutdown,
)
from trading_context.core.exceptions import TradingContextException
from trading_context.core.interfaces import (
    ITradingContextRepository,
    ITradingContextStateStore,
)
from trading_context.core.repository import TradingContextRepository
from trading_context.core.state import TradingContextStateStore
from trading_context.core.orchestrator import TradingContextOrchestrator
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from market_intelligence.core.interfaces import IStateStore
from price_action.core.interfaces import IPatternStateStore
from confluence.core.interfaces import IConfluenceStateStore
from strategy.core.interfaces import IStrategyStateStore

logger = logging.getLogger(__name__)


class TradingContextPlugin(IPlugin):
    """Lifecycle controller and dependency injection binder for the Trading Context."""

    def __init__(
        self,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
        state_store: ITradingContextStateStore | None = None,
        repository: ITradingContextRepository | None = None,
        orchestrator: TradingContextOrchestrator | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container
        self._state_store = state_store
        self._repository = repository
        self._orchestrator = orchestrator

        self._state = ModuleState.CREATED
        self._active_subscriptions: list[tuple[str, Any]] = []

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("trading_context")

    @property
    def name(self) -> str:
        return "Trading Context"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list[PluginId]:
        return [
            PluginId("market_intelligence"),
            PluginId("price_action"),
            PluginId("confluence"),
            PluginId("strategy"),
        ]

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Initialize all subsystems and DI registrations."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Trading Context plugin...")

        # 1. Resolve container dependencies
        if self._container is not None:
            if self._event_bus is None and self._container.has(IEventBus):
                self._event_bus = self._container.resolve(IEventBus)
            if self._config_provider is None and self._container.has(IConfigProvider):
                self._config_provider = self._container.resolve(IConfigProvider)

        if self._event_bus is None:
            self._state = ModuleState.FAILED
            raise TradingContextException(
                "Event Bus is required to initialize the Trading Context plugin."
            )

        # 2. Setup state and repository
        history_limit = 1000
        if self._config_provider is not None:
            history_limit = self._config_provider.get(
                "trading_context.history_limit", 1000
            )

        if self._state_store is None:
            self._state_store = TradingContextStateStore(history_limit=history_limit)

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
            self._repository = TradingContextRepository(storage_engine=storage_engine)

        # 3. Setup Orchestrator
        if self._orchestrator is None:
            self._orchestrator = TradingContextOrchestrator()

        # Try resolving store dependencies for Orchestrator
        market_state_store = None
        pattern_state_store = None
        confluence_state_store = None
        strategy_state_store = None

        if self._container is not None:
            if self._container.has(IStateStore):
                market_state_store = self._container.resolve(IStateStore)
            if self._container.has(IPatternStateStore):
                pattern_state_store = self._container.resolve(IPatternStateStore)
            if self._container.has(IConfluenceStateStore):
                confluence_state_store = self._container.resolve(IConfluenceStateStore)
            if self._container.has(IStrategyStateStore):
                strategy_state_store = self._container.resolve(IStrategyStateStore)

        staleness_threshold = 30.0
        if self._config_provider is not None:
            staleness_threshold = self._config_provider.get(
                "trading_context.staleness_threshold_seconds", 30.0
            )

        self._orchestrator.initialize(
            state_store=self._state_store,
            repository=self._repository,
            event_bus=self._event_bus,
            container=self._container,
            market_state_store=market_state_store,
            pattern_state_store=pattern_state_store,
            confluence_state_store=confluence_state_store,
            strategy_state_store=strategy_state_store,
            staleness_threshold_seconds=staleness_threshold,
        )

        # 4. Register services in DI container
        if self._container is not None:
            if not self._container.has(ITradingContextStateStore):
                self._container.register(
                    ITradingContextStateStore, instance=self._state_store
                )
            if not self._container.has(ITradingContextRepository):
                self._container.register(
                    ITradingContextRepository, instance=self._repository
                )
            if not self._container.has(TradingContextOrchestrator):
                self._container.register(
                    TradingContextOrchestrator, instance=self._orchestrator
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
            "system.confluence_updated", self._on_confluence_updated
        )
        self._subscribe_event(
            "system.strategy_updated", self._on_strategy_updated
        )
        self._subscribe_event(
            "system.strategy_generated", self._on_strategy_generated
        )

        # 6. Publish initialization event
        init_event = TradingContextInitialized(
            source="trading_context.plugin",
            payload={"version": self.version},
        )
        self._event_bus.publish(init_event)

        self._state = ModuleState.RUNNING
        logger.info("Trading Context plugin running successfully ✓")

    def shutdown(self) -> None:
        """Release plugin resources gracefully."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Trading Context plugin...")

        # 1. Unsubscribe event bus subscriptions
        if self._event_bus is not None:
            for event_type, handler in list(self._active_subscriptions):
                try:
                    self._event_bus.unsubscribe(event_type, handler)
                except Exception as e:
                    logger.error(
                        "TradingContext: Failed to unsubscribe from %s: %s",
                        event_type,
                        e,
                    )
        self._active_subscriptions.clear()

        # 2. Publish shutdown event
        if self._event_bus is not None:
            try:
                shutdown_event = TradingContextShutdown(
                    source="trading_context.plugin",
                    payload={"version": self.version},
                )
                self._event_bus.publish(shutdown_event)
            except Exception as e:
                logger.error(
                    "TradingContext: Failed to publish TradingContextShutdown event: %s",
                    e,
                )

        # 3. Clear state store
        if self._state_store is not None:
            try:
                self._state_store.clear()
            except Exception as e:
                logger.error("TradingContext: Error clearing state store: %s", e)

        self._state = ModuleState.STOPPED
        logger.info("Trading Context plugin stopped successfully ✓")

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
            "TradingContext: Received MarketStateUpdated event from %s", event.source
        )
        self._process_event_state(event)

    def _on_pattern_updated(self, event: Any) -> None:
        """Process incoming pattern updates from PAE."""
        logger.debug(
            "TradingContext: Received PatternUpdated event from %s", event.source
        )
        self._process_event_state(event)

    def _on_pattern_quality_updated(self, event: Any) -> None:
        """Process incoming pattern quality updates from PQE."""
        logger.debug(
            "TradingContext: Received PatternQualityUpdated event from %s",
            event.source,
        )
        self._process_event_state(event)

    def _on_confluence_updated(self, event: Any) -> None:
        """Process incoming confluence updates from CE."""
        logger.debug(
            "TradingContext: Received ConfluenceUpdated event from %s",
            event.source,
        )
        self._process_event_state(event)

    def _on_strategy_updated(self, event: Any) -> None:
        """Process incoming strategy updates from SE."""
        logger.debug(
            "TradingContext: Received StrategyUpdated event from %s",
            event.source,
        )
        self._process_event_state(event)

    def _on_strategy_generated(self, event: Any) -> None:
        """Process incoming strategy generated updates from SE."""
        logger.debug(
            "TradingContext: Received StrategyGenerated event from %s",
            event.source,
        )
        self._process_event_state(event)

    def _process_event_state(self, event: Any) -> None:
        if not event or not hasattr(event, "payload") or not event.payload:
            return

        symbol = event.payload.get("symbol")
        timeframe = event.payload.get("timeframe")

        if not (symbol and timeframe):
            # Try to fall back to nested state/pattern/quality/context fields
            for key in ("state", "pattern", "quality", "confluence", "context", "candidate", "match"):
                nested = event.payload.get(key)
                if nested and isinstance(nested, dict):
                    symbol = symbol or nested.get("symbol")
                    timeframe = timeframe or nested.get("timeframe")

        if not (symbol and timeframe):
            return

        try:
            if self._orchestrator is not None:
                self._orchestrator.process_context(symbol, timeframe)
        except Exception as e:
            logger.error(
                "TradingContext: Failed to process event update for %s %s: %s",
                symbol,
                timeframe,
                e,
            )

    @property
    def state_store(self) -> ITradingContextStateStore | None:
        return self._state_store

    @property
    def repository(self) -> ITradingContextRepository | None:
        return self._repository

    @property
    def orchestrator(self) -> TradingContextOrchestrator | None:
        return self._orchestrator
