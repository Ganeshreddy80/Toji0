"""TOJI Platform Shutdown Coordinator.
"""

from __future__ import annotations

import logging
from typing import Any, List
from research_platform.platform.service_registry import ServiceRegistry

logger = logging.getLogger(__name__)


class PlatformShutdownCoordinator:
    """Orchestrates graceful shutdown and cleanup actions in reverse boot order."""

    def __init__(self) -> None:
        self.service_registry = ServiceRegistry()

    def shutdown_platform(self) -> None:
        logger.info("Initiating TOJI V1 Platform Shutdown Sequence...")

        # 1. Shutdown plugins in reverse order
        plugins = self.service_registry.get_service("Plugins")
        if plugins:
            for p in reversed(plugins):
                logger.info("Shutting down Subsystem Plugin: %s", p.__class__.__name__)
                try:
                    p.shutdown()
                except Exception as e:
                    logger.error("Error during plugin %s shutdown: %s", p.__class__.__name__, e)

        # 2. Database Disconnection
        db_manager = self.service_registry.get_service("Database")
        if db_manager:
            try:
                db_manager.disconnect()
            except Exception as e:
                logger.error("Error disconnecting database: %s", e)

        # 3. Clear singletons in ServiceRegistry
        self.service_registry.clear()
        logger.info("TOJI V1 Platform Shutdown Completed gracefully.")
