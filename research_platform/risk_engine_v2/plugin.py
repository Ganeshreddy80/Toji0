"""Risk Engine V2 plugin DI registrations."""

from __future__ import annotations

import logging
from typing import Any
from research_platform.risk_engine_v2.kelly_criterion import KellySizingEngine
from research_platform.risk_engine_v2.exposure_manager import PortfolioExposureManager
from research_platform.risk_engine_v2.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class RiskEngineV2Plugin:
    """Hooks the Risk Engine V2 components into the DI container during boot."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def initialize(self) -> None:
        logger.info("Initializing Risk Engine V2 Plugin...")
        try:
            kelly = KellySizingEngine()
            exposure = PortfolioExposureManager(sector_limits={"TECH": 0.40, "FIN": 0.30})
            cb = CircuitBreaker()

            self.container.register("KellySizingEngine", instance=kelly)
            self.container.register("PortfolioExposureManager", instance=exposure)
            self.container.register("CircuitBreaker", instance=cb)
            
            self.container.register(KellySizingEngine, instance=kelly)
            self.container.register(PortfolioExposureManager, instance=exposure)
            self.container.register(CircuitBreaker, instance=cb)

            logger.info("Risk Engine V2 Plugin initialized successfully.")
        except Exception as e:
            logger.error("Risk Engine V2 Plugin initialization failed: %s", e)

    def shutdown(self) -> None:
        logger.info("Risk Engine V2 Plugin shutdown complete.")

    def health_check(self) -> str:
        return "HEALTHY"
