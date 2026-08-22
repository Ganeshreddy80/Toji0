"""ResearchKernel — the core orchestrator for the Research Platform.

Ties together configuration, registries, lifecycle, event bus,
and dependency injection specifically for isolated research runs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from toji_platform.core.configuration import ConfigurationManager
from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.lifecycle import LifecycleManager
from toji_platform.core.plugin_manager import PluginManager

logger = logging.getLogger(__name__)


class ResearchKernel:
    """Independent kernel bootstrapping and managing research platform services."""

    def __init__(self, config_overrides: Optional[Dict[str, Any]] = None) -> None:
        self._booted = False
        self._config = ConfigurationManager(overrides=config_overrides)
        self._container = Container()
        self._event_bus = InMemoryEventBus()
        self._plugin_manager = PluginManager()
        self._lifecycle = LifecycleManager()

        # Register core services in container
        self._container.register(ConfigurationManager, instance=self._config)
        self._container.register(InMemoryEventBus, instance=self._event_bus)
        self._container.register(PluginManager, instance=self._plugin_manager)
        self._container.register(LifecycleManager, instance=self._lifecycle)

    @property
    def container(self) -> Container:
        """The dependency injection container."""
        return self._container

    @property
    def event_bus(self) -> InMemoryEventBus:
        """The local research event bus."""
        return self._event_bus

    @property
    def config(self) -> ConfigurationManager:
        """The platform configuration manager."""
        return self._config

    def boot(self) -> None:
        """Initialize the kernel and bootstrap plugins."""
        if self._booted:
            return
        
        logger.info("Booting TOJI Research Kernel...")
        
        # Initialize plugins in dependency order
        self._plugin_manager.initialize_all()
        
        # Start lifecycle components
        self._lifecycle.start_all()
        
        self._booted = True
        logger.info("TOJI Research Kernel booted successfully ✓")

    def shutdown(self) -> None:
        """Release resources and shutdown subsystems."""
        if not self._booted:
            return

        logger.info("Shutting down TOJI Research Kernel...")
        
        # Stop lifecycle components
        self._lifecycle.stop_all()
        
        # Shutdown plugins in reverse order
        self._plugin_manager.shutdown_all()
        
        self._booted = False
        logger.info("TOJI Research Kernel shut down cleanly ✓")
