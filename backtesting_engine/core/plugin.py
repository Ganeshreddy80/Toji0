"""Backtesting Engine Subsystem Plugin implementation (Sprint 7A)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from backtesting_engine.core.events import (
    BacktestingEngineInitialized,
    BacktestingEngineShutdown,
)
from backtesting_engine.core.exceptions import BacktestingException
from backtesting_engine.core.interfaces import (
    IBacktestOrchestrator,
    IBacktestRepository,
)
from backtesting_engine.core.orchestrator import BacktestOrchestrator
from backtesting_engine.core.repository import BacktestRepository
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId

logger = logging.getLogger(__name__)


class BacktestingEnginePlugin(IPlugin):
    """Lifecycle controller and dependency injection binder for the Backtesting Engine."""

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        config_provider: Optional[IConfigProvider] = None,
        container: Optional[IContainer] = None,
        repository: Optional[IBacktestRepository] = None,
        orchestrator: Optional[BacktestOrchestrator] = None,
    ) -> None:
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container
        self._repository = repository
        self._orchestrator = orchestrator

        self._state = ModuleState.CREATED
        self._active_subscriptions: list[tuple[str, Any]] = []

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("backtesting_engine")

    @property
    def name(self) -> str:
        return "Backtesting Engine"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list[PluginId]:
        return []

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Initialize all subsystems and DI registrations."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Backtesting Engine plugin...")

        # 1. Resolve container dependencies
        if self._container is not None:
            if self._event_bus is None and self._container.has(IEventBus):
                self._event_bus = self._container.resolve(IEventBus)
            if self._config_provider is None and self._container.has(IConfigProvider):
                self._config_provider = self._container.resolve(IConfigProvider)

        if self._event_bus is None:
            self._state = ModuleState.FAILED
            raise BacktestingException("Event Bus is required to initialize the Backtesting Engine plugin.")

        # 2. Setup Repository & Orchestrator
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
            self._repository = BacktestRepository(storage_engine=storage_engine)

        if self._orchestrator is None:
            self._orchestrator = BacktestOrchestrator()

        self._orchestrator.initialize(
            repository=self._repository,
            event_bus=self._event_bus,
            container=self._container,
        )

        # 3. Register services in DI container
        if self._container is not None:
            if not self._container.has(IBacktestRepository):
                self._container.register(IBacktestRepository, instance=self._repository)
            if not self._container.has(IBacktestOrchestrator):
                self._container.register(IBacktestOrchestrator, instance=self._orchestrator)
            if not self._container.has(BacktestOrchestrator):
                self._container.register(BacktestOrchestrator, instance=self._orchestrator)

        # 4. Publish initialization event
        init_event = BacktestingEngineInitialized(
            source="backtesting.plugin",
            payload={"version": self.version},
        )
        self._event_bus.publish(init_event)

        self._state = ModuleState.RUNNING
        logger.info("Backtesting Engine plugin running successfully ✓")

    def shutdown(self) -> None:
        """Release plugin resources gracefully."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Backtesting Engine plugin...")

        if self._event_bus is not None:
            try:
                shutdown_event = BacktestingEngineShutdown(
                    source="backtesting.plugin",
                    payload={"version": self.version},
                )
                self._event_bus.publish(shutdown_event)
            except Exception as e:
                logger.error("Backtesting Engine: Failed to publish BacktestingEngineShutdown event: %s", e)

        self._state = ModuleState.STOPPED
        logger.info("Backtesting Engine plugin stopped successfully ✓")

    def health_check(self) -> HealthStatus:
        """Return plugin health status."""
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY

        if self._repository is None or self._orchestrator is None:
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    @property
    def repository(self) -> Optional[IBacktestRepository]:
        return self._repository

    @property
    def orchestrator(self) -> Optional[BacktestOrchestrator]:
        return self._orchestrator
