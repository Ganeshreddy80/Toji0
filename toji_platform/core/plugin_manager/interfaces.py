"""Abstract interfaces for the plugin system.

``IPlugin`` defines the lifecycle contract for a single plugin.
``IPluginManager`` defines how the kernel loads and manages plugins.
"""

from __future__ import annotations

import abc

from toji_platform.core.types import HealthStatus, ModuleState, PluginId


class IPlugin(abc.ABC):
    """Contract for a Toji plugin.

    Every plugin must declare its identity, dependencies, and
    implement the lifecycle hooks ``initialize`` / ``shutdown``.
    """

    @property
    @abc.abstractmethod
    def plugin_id(self) -> PluginId:
        """Unique plugin identifier."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable plugin name."""

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Semantic version string."""

    @property
    @abc.abstractmethod
    def dependencies(self) -> list[PluginId]:
        """Plugin IDs this plugin depends on (loaded first)."""

    @property
    @abc.abstractmethod
    def state(self) -> ModuleState:
        """Current lifecycle state."""

    @abc.abstractmethod
    def initialize(self) -> None:
        """Set up the plugin (called after dependencies are ready)."""

    @abc.abstractmethod
    def shutdown(self) -> None:
        """Release resources."""

    @abc.abstractmethod
    def health_check(self) -> HealthStatus:
        """Report plugin health."""


class IPluginManager(abc.ABC):
    """Contract for the plugin manager."""

    @abc.abstractmethod
    def load(self, plugin: IPlugin) -> None:
        """Register and validate a plugin."""

    @abc.abstractmethod
    def unload(self, plugin_id: PluginId) -> None:
        """Unregister a loaded plugin."""

    @abc.abstractmethod
    def get(self, plugin_id: PluginId) -> IPlugin:
        """Retrieve a loaded plugin by ID."""

    @abc.abstractmethod
    def list_plugins(self) -> list[IPlugin]:
        """Return all loaded plugins."""

    @abc.abstractmethod
    def initialize_all(self) -> None:
        """Initialize all loaded plugins in dependency order."""

    @abc.abstractmethod
    def shutdown_all(self) -> None:
        """Shut down all plugins in reverse dependency order."""

    @abc.abstractmethod
    def health_check_all(self) -> dict[PluginId, HealthStatus]:
        """Run health checks on all plugins."""
