"""Strategy Framework plugin mapping registrations inside DI container."""

from __future__ import annotations

import logging
from typing import Any

from research_platform.strategy_framework.composer import StrategyComposer
from research_platform.strategy_framework.loader import StrategyLoader
from research_platform.strategy_framework.registry import StrategyFrameworkRegistry

logger = logging.getLogger(__name__)


class StrategyFrameworkPlugin:
    """Hooks the Strategy Framework into the DI container during boot."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def initialize(self) -> None:
        logger.info("Initializing Strategy Framework Plugin...")
        try:
            composer = StrategyComposer()
            loader = StrategyLoader()
            registry = StrategyFrameworkRegistry()

            self.container.register("StrategyComposer", instance=composer)
            self.container.register("StrategyLoader", instance=loader)
            self.container.register("StrategyFrameworkRegistry", instance=registry)
            
            self.container.register(StrategyComposer, instance=composer)
            self.container.register(StrategyLoader, instance=loader)
            self.container.register(StrategyFrameworkRegistry, instance=registry)

            logger.info("Strategy Framework Plugin initialized successfully.")
        except Exception as e:
            logger.error("Strategy Framework Plugin initialization failed: %s", e)

    def shutdown(self) -> None:
        logger.info("Strategy Framework Plugin shutdown complete.")

    def health_check(self) -> str:
        return "HEALTHY"
