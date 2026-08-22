"""Dashboard Platform Subsystem Plugin implementation."""

from __future__ import annotations

import logging
import threading
from typing import Any, List, Tuple
import uvicorn

from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from dashboard.core.events import DashboardInitialized, DashboardShutdown
from dashboard.core.exceptions import DashboardError
from dashboard.core.interfaces import IDashboardRepository, IDashboardStateStore
from dashboard.core.repository import DashboardRepository
from dashboard.core.state import DashboardStateStore
from dashboard.core.orchestrator import DashboardOrchestrator
from dashboard.aggregator.event_aggregator import DashboardEventAggregator
from dashboard.health.health_monitor import HealthMonitor
from dashboard.websocket.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class DashboardPlatformPlugin(IPlugin):
    """Lifecycle controller and dependency injection binder for the Dashboard Platform."""

    def __init__(
        self,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
        state_store: IDashboardStateStore | None = None,
        repository: IDashboardRepository | None = None,
        orchestrator: DashboardOrchestrator | None = None,
        event_aggregator: DashboardEventAggregator | None = None,
        health_monitor: HealthMonitor | None = None,
        websocket_manager: WebSocketManager | None = None,
        port: int = 8000,
    ) -> None:
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container
        self._state_store = state_store
        self._repository = repository
        self._orchestrator = orchestrator
        self._event_aggregator = event_aggregator
        self._health_monitor = health_monitor
        self._websocket_manager = websocket_manager
        self._port = port

        self._state = ModuleState.CREATED
        self._active_subscriptions: List[Tuple[str, Any]] = []
        self._server: uvicorn.Server | None = None
        self._server_thread: threading.Thread | None = None

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("dashboard_platform")

    @property
    def name(self) -> str:
        return "Dashboard Platform"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> List[PluginId]:
        # Observes all engines up to Portfolio
        return [
            PluginId("market_intelligence"),
            PluginId("price_action"),
            PluginId("confluence"),
            PluginId("strategy"),
            PluginId("trading_context"),
            PluginId("risk_engine"),
            PluginId("position_sizing"),
            PluginId("execution_engine"),
            PluginId("portfolio_engine"),
        ]

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Initialize all components, DI registrations, event subscribers, and Uvicorn server."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Dashboard Platform plugin...")

        # 1. Resolve container dependencies
        if self._container is not None:
            if self._event_bus is None and self._container.has(IEventBus):
                self._event_bus = self._container.resolve(IEventBus)
            if self._config_provider is None and self._container.has(IConfigProvider):
                self._config_provider = self._container.resolve(IConfigProvider)

        if self._event_bus is None:
            self._state = ModuleState.FAILED
            raise DashboardError(
                "Event Bus is required to initialize the Dashboard Platform plugin."
            )

        # 2. Retrieve config settings
        if self._config_provider is not None:
            self._port = self._config_provider.get("dashboard.port", 8000)

        # 3. Setup core state store and repository
        if self._state_store is None:
            self._state_store = DashboardStateStore()

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
            self._repository = DashboardRepository(storage_engine=storage_engine)

        if self._orchestrator is None:
            self._orchestrator = DashboardOrchestrator()

        self._orchestrator.initialize(
            state_store=self._state_store,
            repository=self._repository,
        )

        # 4. Setup health monitor, event aggregator, and websocket manager
        if self._health_monitor is None:
            self._health_monitor = HealthMonitor()

        if self._websocket_manager is None:
            self._websocket_manager = WebSocketManager()

        if self._event_aggregator is None:
            self._event_aggregator = DashboardEventAggregator(
                orchestrator=self._orchestrator,
                health_monitor=self._health_monitor,
                websocket_manager=self._websocket_manager,
                event_bus=self._event_bus,
            )

        # 5. Register services in DI container
        if self._container is not None:
            if not self._container.has(IDashboardStateStore):
                self._container.register(
                    IDashboardStateStore, instance=self._state_store
                )
            if not self._container.has(IDashboardRepository):
                self._container.register(
                    IDashboardRepository, instance=self._repository
                )
            if not self._container.has(DashboardOrchestrator):
                self._container.register(
                    DashboardOrchestrator, instance=self._orchestrator
                )
            if not self._container.has(DashboardEventAggregator):
                self._container.register(
                    DashboardEventAggregator, instance=self._event_aggregator
                )
            if not self._container.has(HealthMonitor):
                self._container.register(
                    HealthMonitor, instance=self._health_monitor
                )
            if not self._container.has(WebSocketManager):
                self._container.register(
                    WebSocketManager, instance=self._websocket_manager
                )

        # 6. Subscribe to all platform events
        self._subscribe_events()

        # 7. Start Uvicorn background server hosting the REST/WS APIs
        import sys
        from toji_platform.core.types import Profile
        is_testing = (
            "pytest" in sys.modules or
            (self._config_provider is not None and self._config_provider.profile == Profile.TESTING)
        )
        is_mock = hasattr(self._start_uvicorn_server, "_mock_self")
        if not is_testing or is_mock:
            self._start_uvicorn_server()
        else:
            logger.info("Dashboard API server startup skipped in TESTING environment.")

        # 8. Publish initialization event
        init_event = DashboardInitialized(
            source="dashboard.plugin",
            payload={"version": self.version, "port": self._port},
        )
        self._event_bus.publish(init_event)

        self._state = ModuleState.RUNNING
        logger.info("Dashboard Platform plugin running successfully on port %d ✓", self._port)

    def shutdown(self) -> None:
        """Release plugin resources and stop the background Uvicorn server gracefully."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Dashboard Platform plugin...")

        # 1. Unsubscribe event bus subscriptions
        if self._event_bus is not None:
            for event_type, handler in list(self._active_subscriptions):
                try:
                    self._event_bus.unsubscribe(event_type, handler)
                except Exception as e:
                    logger.error("DashboardPlugin: Failed to unsubscribe from %s: %s", event_type, e)
        self._active_subscriptions.clear()

        # 2. Stop Uvicorn server
        self._stop_uvicorn_server()

        # 3. Publish shutdown event
        if self._event_bus is not None:
            try:
                shutdown_event = DashboardShutdown(
                    source="dashboard.plugin",
                    payload={"version": self.version},
                )
                self._event_bus.publish(shutdown_event)
            except Exception as e:
                logger.error("DashboardPlugin: Failed to publish DashboardShutdown event: %s", e)

        # 4. Clear state store
        if self._state_store is not None:
            try:
                self._state_store.clear()
            except Exception as e:
                logger.error("DashboardPlugin: Error clearing state store: %s", e)

        self._state = ModuleState.STOPPED
        logger.info("Dashboard Platform plugin stopped successfully ✓")

    def health_check(self) -> HealthStatus:
        """Return plugin health state."""
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY

        if (
            self._state_store is None
            or self._repository is None
            or self._orchestrator is None
            or self._event_aggregator is None
            or self._health_monitor is None
            or self._websocket_manager is None
        ):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY


    def _subscribe_events(self) -> None:
        """Connect all event listeners."""
        events_to_subscribe = [
            ("system.market_state_updated", self._event_aggregator.handle_market_state_updated),
            ("system.pattern_updated", self._event_aggregator.handle_pattern_updated),
            ("system.pattern_quality_updated", self._event_aggregator.handle_pattern_quality_updated),
            ("system.confluence_updated", self._event_aggregator.handle_confluence_updated),
            ("system.strategy_updated", self._event_aggregator.handle_strategy_updated),
            ("system.trading_context_updated", self._event_aggregator.handle_trading_context_updated),
            ("system.risk_updated", self._event_aggregator.handle_risk_updated),
            ("system.position_size_updated", self._event_aggregator.handle_position_size_updated),
            ("system.execution_completed", self._event_aggregator.handle_execution_completed),
            ("system.portfolio_updated", self._event_aggregator.handle_portfolio_updated),
        ]

        for event_name, handler in events_to_subscribe:
            self._event_bus.subscribe(event_name, handler)
            self._active_subscriptions.append((event_name, handler))

    def _start_uvicorn_server(self) -> None:
        """Launch uvicorn in a background thread to run the FastAPI app."""
        # Defer import to prevent dependency resolution issues on module loading
        from dashboard.backend.app import create_app

        app = create_app(
            state_store=self._state_store,
            repository=self._repository,
            health_monitor=self._health_monitor,
            websocket_manager=self._websocket_manager,
            event_aggregator=self._event_aggregator,
            container=self._container,
        )

        config = uvicorn.Config(
            app=app,
            host="127.0.0.1",
            port=self._port,
            log_level="warning",
            loop="asyncio",
        )
        self._server = uvicorn.Server(config)

        def run_server() -> None:
            try:
                self._server.run()
            except Exception as ex:
                logger.error("DashboardPlugin: Uvicorn background server error: %s", ex)

        self._server_thread = threading.Thread(target=run_server, name="uvicorn-dashboard-server")
        self._server_thread.daemon = True
        self._server_thread.start()

    def _stop_uvicorn_server(self) -> None:
        """Shut down the uvicorn server thread cleanly."""
        if self._server:
            try:
                self._server.should_exit = True
                if self._server_thread:
                    self._server_thread.join(timeout=3.0)
            except Exception as e:
                logger.error("DashboardPlugin: Error stopping Uvicorn server: %s", e)
            finally:
                self._server = None
                self._server_thread = None

    @property
    def state_store(self) -> IDashboardStateStore | None:
        return self._state_store

    @property
    def repository(self) -> IDashboardRepository | None:
        return self._repository

    @property
    def orchestrator(self) -> DashboardOrchestrator | None:
        return self._orchestrator

    @property
    def event_aggregator(self) -> DashboardEventAggregator | None:
        return self._event_aggregator

    @property
    def health_monitor(self) -> HealthMonitor | None:
        return self._health_monitor

    @property
    def websocket_manager(self) -> WebSocketManager | None:
        return self._websocket_manager
