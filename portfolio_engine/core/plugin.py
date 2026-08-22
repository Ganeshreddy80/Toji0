from __future__ import annotations

import logging
from typing import Any, List, Tuple

from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from portfolio_engine.core.state import PortfolioStateStore
from portfolio_engine.core.repository import PortfolioRepository
from portfolio_engine.core.orchestrator import PortfolioOrchestrator
from portfolio_engine.core.exceptions import PortfolioEngineError

logger = logging.getLogger(__name__)


class PortfolioPlatformPlugin(IPlugin):
    """Lifecycle controller and dependency injection binder for the Portfolio Engine."""

    def __init__(
        self,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
        state_store: PortfolioStateStore | None = None,
        repository: PortfolioRepository | None = None,
        orchestrator: PortfolioOrchestrator | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container
        self._state_store = state_store
        self._repository = repository
        self._orchestrator = orchestrator

        self._state = ModuleState.CREATED
        self._active_subscriptions: List[Tuple[str, Any]] = []

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("portfolio_engine")

    @property
    def name(self) -> str:
        return "Portfolio Engine"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> List[PluginId]:
        return [PluginId("execution_engine")]

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Initialize all subsystems, DI registrations, and event subscribers."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Portfolio Engine plugin...")

        # 1. Resolve container dependencies
        if self._container is not None:
            if self._event_bus is None and self._container.has(IEventBus):
                self._event_bus = self._container.resolve(IEventBus)
            if self._config_provider is None and self._container.has(IConfigProvider):
                self._config_provider = self._container.resolve(IConfigProvider)

        if self._event_bus is None:
            self._state = ModuleState.FAILED
            raise PortfolioEngineError("Event Bus is required to initialize the Portfolio Engine plugin.")

        # 2. Get configurations
        initial_balance = 100000.0
        if self._config_provider:
            initial_balance = self._config_provider.get("portfolio.initial_balance", 100000.0)

        # 3. Instantiate core components
        if self._state_store is None:
            self._state_store = PortfolioStateStore(initial_balance=initial_balance)
        if self._repository is None:
            self._repository = PortfolioRepository()
        if self._orchestrator is None:
            self._orchestrator = PortfolioOrchestrator()

        self._orchestrator.initialize(
            state_store=self._state_store,
            repository=self._repository,
            event_bus=self._event_bus,
            container=self._container,
        )

        # 4. DI Registrations
        if self._container is not None:
            self._container.register(PortfolioStateStore, self._state_store)
            self._container.register(PortfolioRepository, self._repository)
            self._container.register(PortfolioOrchestrator, self._orchestrator)

        # 5. Subscribe to execution completed events
        self._subscribe_events()

        self._state = ModuleState.RUNNING
        logger.info("Portfolio Engine plugin initialized successfully ✓")

    def shutdown(self) -> None:
        """Release plugin resources and unsubscribe event hooks."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Portfolio Engine plugin...")

        if self._event_bus is not None:
            for event_type, handler in list(self._active_subscriptions):
                try:
                    self._event_bus.unsubscribe(event_type, handler)
                except Exception as e:
                    logger.error("PortfolioPlugin: Failed to unsubscribe from %s: %s", event_type, e)
        self._active_subscriptions.clear()

        if self._state_store:
            self._state_store.clear()
        if self._repository:
            self._repository.clear()

        self._state = ModuleState.STOPPED
        logger.info("Portfolio Engine plugin stopped successfully ✓")

    def health_check(self) -> HealthStatus:
        """Return operational health status."""
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY
        if self._state_store is None or self._repository is None or self._orchestrator is None:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def _subscribe_events(self) -> None:
        """Connect all event listeners to the Platform Event Bus."""
        events_to_subscribe = [
            ("system.execution_completed", self._orchestrator.on_execution_completed),
            ("system.execution_partial_fill", self._orchestrator.on_execution_partial_fill),
            ("system.execution_cancelled", self._orchestrator.on_execution_cancelled),
        ]

        for event_name, handler in events_to_subscribe:
            self._event_bus.subscribe(event_name, handler)
            self._active_subscriptions.append((event_name, handler))
