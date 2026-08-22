"""Base data provider class implementing IProvider and IPlugin lifecycle."""

from __future__ import annotations

import logging
from typing import Any

from data.providers.interfaces import IProvider
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId

logger = logging.getLogger(__name__)


class BaseProvider(IProvider, IPlugin):
    """Bridge base class combining IProvider and IPlugin contracts.

    Concrete providers should inherit from this class and override methods
    as appropriate.
    """

    def __init__(self, kernel: Any = None) -> None:
        self._kernel = kernel
        self._state = ModuleState.CREATED
        self._health = HealthStatus.HEALTHY

    # ── IPlugin Identification ───────────────────────────────────────────

    @property
    def plugin_id(self) -> PluginId:
        """Derive plugin identifier from lowercase provider name."""
        return PluginId(f"provider_{self.name.lower().replace(' ', '_')}")

    @property
    def version(self) -> str:
        """Default provider plugin version."""
        return "0.1.0"

    @property
    def dependencies(self) -> list[PluginId]:
        """Default provider dependencies (none)."""
        return []

    @property
    def state(self) -> ModuleState:
        """Current module state."""
        return self._state

    # ── Lifecycles ───────────────────────────────────────────────────────

    def initialize(self, kernel: Any = None) -> None:
        """Initialize connection parameters or client configurations.

        Can be called with or without a kernel reference.
        """
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        if kernel is not None:
            self._kernel = kernel

        logger.info("Initializing data provider: %s", self.name)
        self._do_initialize()
        self._state = ModuleState.RUNNING

    def shutdown(self) -> None:
        """Stop websockets or database sessions, releasing resources."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down data provider: %s", self.name)
        self._do_shutdown()
        self._state = ModuleState.STOPPED

    def health_check(self) -> HealthStatus:
        """Query connection health/liveness status."""
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY
        return self._do_health_check()

    # ── Extension hooks ──────────────────────────────────────────────────

    def _do_initialize(self) -> None:
        """Hook for concrete subclasses to initialize resources."""
        pass

    def _do_shutdown(self) -> None:
        """Hook for concrete subclasses to release resources."""
        pass

    def _do_health_check(self) -> HealthStatus:
        """Hook for concrete subclasses to run health checks."""
        return HealthStatus.HEALTHY
