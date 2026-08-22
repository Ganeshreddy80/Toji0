"""Feature Platform Plugin interface mapping for Toji.
"""

from __future__ import annotations

import logging
from typing import List, Callable, Any

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId

from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
from research_platform.feature_platform.events import FeatureCalculated, FeatureValidated

logger = logging.getLogger(__name__)


class FeaturePlatformPlugin(IPlugin):
    """Integrates the Feature Platform inside the Research DI container."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._state = ModuleState.CREATED
        self._event_bus: IEventBus | None = None
        self._subscriptions: List[tuple[str, Callable[[Any], None]]] = []

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("feature_platform")

    @property
    def name(self) -> str:
        return "Feature Platform"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> List[PluginId]:
        # Enforces low-level research layers loaded first
        return []

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Register the orchestrator in the container and bootstrap default production features."""
        self._event_bus = self._container.resolve(IEventBus)
        orchestrator = FeaturePlatformOrchestrator(self._event_bus)
        orchestrator.register_default_features()
        
        self._container.register(FeaturePlatformOrchestrator, instance=orchestrator)
        self._container.register("FeaturePlatformOrchestrator", instance=orchestrator)
        
        self._subscriptions = [
            ("system.feature_calculated", self._log_event),
            ("system.feature_validated", self._log_event),
        ]
        
        for event_type, handler in self._subscriptions:
            self._event_bus.subscribe(event_type, handler)
        
        self._state = ModuleState.RUNNING

    def shutdown(self) -> None:
        """Shutdown hooks."""
        if self._event_bus:
            for event_type, handler in self._subscriptions:
                self._event_bus.unsubscribe(event_type, handler)
        self._subscriptions = []
        self._state = ModuleState.STOPPED

    def health_check(self) -> HealthStatus:
        """Return operational health status."""
        return HealthStatus(status="HEALTHY")

    def _log_event(self, event: Any) -> None:
        """FP-6 Option A observability handler — DEBUG log only.

        Executes synchronously on the publishing thread (InMemoryEventBus is
        synchronous).  Must stay lightweight: no computation, no FeatureStore
        mutation, no blocking I/O, no recursive publish.
        """
        payload = getattr(event, "payload", {}) or {}
        logger.debug(
            "FP event: %s | name=%s version=%s symbol=%s approved=%s",
            type(event).__name__,
            payload.get("name", "?"),
            payload.get("version", "?"),
            payload.get("symbol", "?"),
            payload.get("approved", "?"),
        )
