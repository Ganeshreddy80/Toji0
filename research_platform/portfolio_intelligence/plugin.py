"""Portfolio Intelligence plugin DI registrations."""

from __future__ import annotations

import logging
from typing import Any
from research_platform.portfolio_intelligence.metrics import PortfolioMetricsCalculator
from research_platform.portfolio_intelligence.rebalancer import PortfolioRebalancer

logger = logging.getLogger(__name__)


class PortfolioIntelligencePlugin:
    """Hooks the Portfolio Intelligence components into the DI container during boot."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def initialize(self) -> None:
        logger.info("Initializing Portfolio Intelligence Plugin...")
        try:
            from research_platform.portfolio_intelligence.analytics import AdvancedPortfolioAnalytics
            calc = PortfolioMetricsCalculator()
            rebalancer = PortfolioRebalancer()
            analytics = AdvancedPortfolioAnalytics()

            self.container.register("PortfolioMetricsCalculator", instance=calc)
            self.container.register("PortfolioRebalancer", instance=rebalancer)
            self.container.register("AdvancedPortfolioAnalytics", instance=analytics)
            
            self.container.register(PortfolioMetricsCalculator, instance=calc)
            self.container.register(PortfolioRebalancer, instance=rebalancer)
            self.container.register(AdvancedPortfolioAnalytics, instance=analytics)

            logger.info("Portfolio Intelligence Plugin initialized successfully.")
        except Exception as e:
            logger.error("Portfolio Intelligence Plugin initialization failed: %s", e)

    def shutdown(self) -> None:
        logger.info("Portfolio Intelligence Plugin shutdown complete.")

    def health_check(self) -> str:
        return "HEALTHY"
