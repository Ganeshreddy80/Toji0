"""Research Platform Subsystem Plugin implementation (Sprint 6)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from research_platform.core.events import (
    ResearchPlatformInitialized,
    ResearchPlatformShutdown,
)
from research_platform.core.exceptions import ResearchPlatformException
from research_platform.core.interfaces import (
    IDatasetManager,
    IExperimentManager,
    IExperimentRepository,
    IStrategyRegistry,
)
from research_platform.core.orchestrator import ResearchOrchestrator
from research_platform.core.repository import ResearchExperimentRepository
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId

logger = logging.getLogger(__name__)


class ResearchPlatformPlugin(IPlugin):
    """Lifecycle controller and dependency injection binder for the Research Platform."""

    def __init__(
        self,
        event_bus: Optional[Any] = None,
        config_provider: Optional[IConfigProvider] = None,
        container: Optional[IContainer] = None,
        repository: Optional[IExperimentRepository] = None,
        orchestrator: Optional[ResearchOrchestrator] = None,
    ) -> None:
        # If PluginLoader passed container as the first positional argument
        if event_bus is not None and hasattr(event_bus, "resolve") and not hasattr(event_bus, "publish"):
            container = event_bus
            event_bus = None

        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container
        self._repository = repository
        self._orchestrator = orchestrator

        self._state = ModuleState.CREATED
        self._active_subscriptions: list[tuple[str, Any]] = []

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("research_platform")

    @property
    def name(self) -> str:
        return "Research Platform"

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
        logger.info("Initializing Research Platform plugin...")

        # 1. Resolve container dependencies
        if self._container is not None:
            if self._event_bus is None:
                if self._container.has("IEventBus"):
                    self._event_bus = self._container.resolve("IEventBus")
                elif self._container.has(IEventBus):
                    self._event_bus = self._container.resolve(IEventBus)
            if self._config_provider is None:
                if self._container.has("IConfigProvider"):
                    self._config_provider = self._container.resolve("IConfigProvider")
                elif self._container.has(IConfigProvider):
                    self._config_provider = self._container.resolve(IConfigProvider)

        if self._event_bus is None:
            self._state = ModuleState.FAILED
            raise ResearchPlatformException("Event Bus is required to initialize the Research Platform plugin.")

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
            self._repository = ResearchExperimentRepository(storage_engine=storage_engine)

        if self._orchestrator is None:
            self._orchestrator = ResearchOrchestrator()

        self._orchestrator.initialize(
            repository=self._repository,
            event_bus=self._event_bus,
            container=self._container,
        )

        # 3. Register services in DI container
        if self._container is not None:
            if not self._container.has(IExperimentRepository):
                self._container.register(IExperimentRepository, instance=self._repository)
            if not self._container.has(IExperimentManager):
                self._container.register(IExperimentManager, instance=self._orchestrator)
            if not self._container.has(IDatasetManager):
                self._container.register(IDatasetManager, instance=self._orchestrator.dataset_manager)
            if not self._container.has(IStrategyRegistry):
                self._container.register(IStrategyRegistry, instance=self._orchestrator.strategy_registry)
            if not self._container.has(ResearchOrchestrator):
                self._container.register(ResearchOrchestrator, instance=self._orchestrator)

        # 4. Publish initialization event
        init_event = ResearchPlatformInitialized(
            source="research.plugin",
            payload={"version": self.version},
        )
        self._event_bus.publish(init_event)

        self._state = ModuleState.RUNNING
        logger.info("Research Platform plugin running successfully ✓")

    def shutdown(self) -> None:
        """Release plugin resources gracefully."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Research Platform plugin...")

        # 1. Unsubscribe event bus subscriptions
        if self._event_bus is not None:
            for event_type, handler in list(self._active_subscriptions):
                try:
                    self._event_bus.unsubscribe(event_type, handler)
                except Exception as e:
                    logger.error("Research Platform: Failed to unsubscribe from %s: %s", event_type, e)
        self._active_subscriptions.clear()

        # 2. Publish shutdown event
        if self._event_bus is not None:
            try:
                shutdown_event = ResearchPlatformShutdown(
                    source="research.plugin",
                    payload={"version": self.version},
                )
                self._event_bus.publish(shutdown_event)
            except Exception as e:
                logger.error("Research Platform: Failed to publish ResearchPlatformShutdown event: %s", e)

        self._state = ModuleState.STOPPED
        logger.info("Research Platform plugin stopped successfully ✓")

    def health_check(self) -> HealthStatus:
        """Return plugin status."""
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY

        if self._repository is None or self._orchestrator is None:
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    @property
    def repository(self) -> Optional[IExperimentRepository]:
        return self._repository

    @property
    def orchestrator(self) -> Optional[ResearchOrchestrator]:
        return self._orchestrator
