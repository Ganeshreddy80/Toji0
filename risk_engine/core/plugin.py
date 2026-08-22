"""Risk Engine Subsystem Plugin implementation."""

from __future__ import annotations

import logging
from typing import Any

from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from trading_context.core.models import TradingContext
from risk_engine.core.events import (
    RiskInitialized,
    RiskShutdown,
)
from risk_engine.core.exceptions import RiskException
from risk_engine.core.interfaces import (
    IRiskRepository,
    IRiskStateStore,
    IRiskEngine,
)
from risk_engine.core.repository import RiskRepository
from risk_engine.core.state import RiskStateStore
from risk_engine.analysis.risk_engine import RiskEngine
from risk_engine.core.orchestrator import RiskOrchestrator

logger = logging.getLogger(__name__)


class RiskEnginePlugin(IPlugin):
    """Lifecycle controller and dependency injection binder for the Risk Engine."""

    def __init__(
        self,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
        state_store: IRiskStateStore | None = None,
        repository: IRiskRepository | None = None,
        risk_engine: IRiskEngine | None = None,
        orchestrator: RiskOrchestrator | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container
        self._state_store = state_store
        self._repository = repository
        self._risk_engine = risk_engine
        self._orchestrator = orchestrator

        self._state = ModuleState.CREATED
        self._active_subscriptions: list[tuple[str, Any]] = []

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("risk_engine")

    @property
    def name(self) -> str:
        return "Risk Engine"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list[PluginId]:
        # Depends on Trading Context which produces the TradingContext snapshots
        return [PluginId("trading_context")]

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Initialize all subsystems, DI registrations, and event subscribers."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Risk Engine plugin...")

        # 1. Resolve container dependencies
        if self._container is not None:
            if self._event_bus is None and self._container.has(IEventBus):
                self._event_bus = self._container.resolve(IEventBus)
            if self._config_provider is None and self._container.has(IConfigProvider):
                self._config_provider = self._container.resolve(IConfigProvider)

        if self._event_bus is None:
            self._state = ModuleState.FAILED
            raise RiskException(
                "Event Bus is required to initialize the Risk Engine plugin."
            )

        # 2. Setup state and repository
        history_limit = 1000
        if self._config_provider is not None:
            history_limit = self._config_provider.get(
                "risk.history_limit", 1000
            )

        if self._state_store is None:
            self._state_store = RiskStateStore(history_limit=history_limit)

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
            self._repository = RiskRepository(storage_engine=storage_engine)

        # 3. Setup risk engine and orchestrator
        if self._risk_engine is None:
            self._risk_engine = RiskEngine()

        if self._orchestrator is None:
            self._orchestrator = RiskOrchestrator()

        self._orchestrator.initialize(
            state_store=self._state_store,
            repository=self._repository,
            risk_engine=self._risk_engine,
            event_bus=self._event_bus,
            config_provider=self._config_provider,
            container=self._container,
        )

        # 4. Register services in DI container
        if self._container is not None:
            if not self._container.has(IRiskStateStore):
                self._container.register(
                    IRiskStateStore, instance=self._state_store
                )
            if not self._container.has(IRiskRepository):
                self._container.register(
                    IRiskRepository, instance=self._repository
                )
            if not self._container.has(IRiskEngine):
                self._container.register(
                    IRiskEngine, instance=self._risk_engine
                )
            if not self._container.has(RiskOrchestrator):
                self._container.register(
                    RiskOrchestrator, instance=self._orchestrator
                )

        # 5. Subscribe to context and execution events
        self._subscribe_event(
            "system.trading_context_created", self._on_trading_context_created
        )
        self._subscribe_event(
            "system.trading_context_updated", self._on_trading_context_updated
        )
        self._subscribe_event(
            "system.execution_requested", self._on_execution_requested
        )

        # 6. Publish initialization event
        init_event = RiskInitialized(
            source="risk_engine.plugin",
            payload={"version": self.version},
        )
        self._event_bus.publish(init_event)

        self._state = ModuleState.RUNNING
        logger.info("Risk Engine plugin running successfully ✓")

    def shutdown(self) -> None:
        """Release plugin resources gracefully."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Risk Engine plugin...")

        # 1. Unsubscribe event bus subscriptions
        if self._event_bus is not None:
            for event_type, handler in list(self._active_subscriptions):
                try:
                    self._event_bus.unsubscribe(event_type, handler)
                except Exception as e:
                    logger.error(
                        "RiskEngine: Failed to unsubscribe from %s: %s",
                        event_type,
                        e,
                    )
        self._active_subscriptions.clear()

        # 2. Publish shutdown event
        if self._event_bus is not None:
            try:
                shutdown_event = RiskShutdown(
                    source="risk_engine.plugin",
                    payload={"version": self.version},
                )
                self._event_bus.publish(shutdown_event)
            except Exception as e:
                logger.error(
                    "RiskEngine: Failed to publish RiskShutdown event: %s",
                    e,
                )

        # 3. Clear state store
        if self._state_store is not None:
            try:
                self._state_store.clear()
            except Exception as e:
                logger.error("RiskEngine: Error clearing state store: %s", e)

        self._state = ModuleState.STOPPED
        logger.info("Risk Engine plugin stopped successfully ✓")

    def health_check(self) -> HealthStatus:
        """Return plugin health state."""
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY

        if (
            self._state_store is None
            or self._repository is None
            or self._risk_engine is None
            or self._orchestrator is None
        ):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def _subscribe_event(self, event_type: str, handler: Any) -> None:
        """Connect callback handler in the event bus."""
        self._event_bus.subscribe(event_type, handler)
        self._active_subscriptions.append((event_type, handler))

    def _on_trading_context_created(self, event: Any) -> None:
        """Trigger evaluation when a new trading context is created."""
        logger.debug(
            "RiskEngine: Received TradingContextCreated event from %s", event.source
        )
        self._process_event_context(event)

    def _on_trading_context_updated(self, event: Any) -> None:
        """Trigger evaluation when a trading context is updated."""
        logger.debug(
            "RiskEngine: Received TradingContextUpdated event from %s", event.source
        )
        self._process_event_context(event)

    def _on_execution_requested(self, event: Any) -> None:
        """Trigger risk engine rules validation for an execution request."""
        logger.debug(
            "RiskEngine: Received ExecutionRequested event from %s", event.source
        )
        if not event or not hasattr(event, "payload") or not event.payload:
            return
        try:
            if self._orchestrator is not None:
                self._orchestrator.process_execution_request(event.payload)
        except Exception as e:
            logger.error("RiskEngine: Failed to process execution request event: %s", e)

    def _process_event_context(self, event: Any) -> None:
        if not event or not hasattr(event, "payload") or not event.payload:
            return

        context_dict = event.payload.get("context")
        if not context_dict or not isinstance(context_dict, dict):
            return

        try:
            # Reconstruct TradingContext from dictionary
            context = TradingContext(**context_dict)
            if self._orchestrator is not None:
                self._orchestrator.process_context(context)
        except Exception as e:
            logger.error(
                "RiskEngine: Failed to process trading context from event: %s",
                e,
            )

    @property
    def state_store(self) -> IRiskStateStore | None:
        return self._state_store

    @property
    def repository(self) -> IRiskRepository | None:
        return self._repository

    @property
    def risk_engine(self) -> IRiskEngine | None:
        return self._risk_engine

    @property
    def orchestrator(self) -> RiskOrchestrator | None:
        return self._orchestrator
