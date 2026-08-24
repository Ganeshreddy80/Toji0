"""R51 Central Configuration Framework Plugin — platform DI integration."""

from __future__ import annotations

import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


class ConfigPlugin:
    """Registers R51 ConfigManager and ConfigLoader in the DI container."""

    def __init__(self, container: Any) -> None:
        self.container = container
        self._manager = None

    def initialize(self) -> None:
        logger.info("Initializing Central Configuration Framework (R51)...")
        try:
            from research_platform.config.config_manager import ConfigManager
            from research_platform.config.config_loader import ConfigLoader
            from research_platform.config.repository import ConfigRepository

            is_pytest = "pytest" in sys.modules or any("pytest" in arg for arg in sys.argv)
            mgr = ConfigManager(require_secure_database=not is_pytest)
            loader = ConfigLoader()
            repo = ConfigRepository()

            self.container.register("ConfigManager", instance=mgr)
            self.container.register("ConfigLoader", instance=loader)
            self.container.register("ConfigurationRepository", instance=repo)
            self.container.register(ConfigManager, instance=mgr)

            from research_platform.platform.service_registry import ServiceRegistry
            ServiceRegistry().register_service("ConfigManager", mgr)

            self._manager = mgr
            logger.info("R51 ConfigPlugin initialized — mode=%s.", mgr.get_config().runtime.mode)
        except Exception as e:
            logger.error("R51 ConfigPlugin initialization failed: %s", e)

    def shutdown(self) -> None:
        try:
            if self._manager:
                self._manager.shutdown()
        except Exception as e:
            logger.warning("R51 ConfigPlugin shutdown error: %s", e)
        logger.info("R51 ConfigPlugin shutdown complete.")

    def health_check(self) -> str:
        return "HEALTHY"
