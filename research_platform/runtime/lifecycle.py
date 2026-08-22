"""Runtime lifecycle and startup coordinator.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from research_platform.platform.startup import PlatformStartupCoordinator
from research_platform.platform.service_registry import ServiceRegistry

logger = logging.getLogger(__name__)


class RuntimeLifecycleManager:
    """Manages TOJI bootstrap and clean shutdown sequences."""

    def __init__(self) -> None:
        self.coordinator = PlatformStartupCoordinator()

    def boot(self) -> ServiceRegistry:
        """Execute complete boot sequence pipeline."""
        logger.info("Initializing Continuous Runtime Lifecycle Boot...")
        
        # 1-7. Run standard startup coordinator boot (Config, DB, Migrations, EventBus, DI Container, Plugins)
        self.coordinator.boot_platform()
        registry = self.coordinator.service_registry
        container = registry.get_service("Container")

        # 8. Load Memory
        logger.info("Restoring Institutional Memory state...")
        try:
            mem_orch = container.resolve("InstitutionalMemoryOrchestrator")
            if mem_orch and hasattr(mem_orch, "load_memory"):
                mem_orch.load_memory()
        except Exception as e:
            logger.warning("Failed to restore Institutional Memory state: %s", e)

        # 9. Load Knowledge Graph
        logger.info("Restoring Confluence Knowledge Graph...")
        try:
            kg_orch = container.resolve("KnowledgeGraphOrchestrator")
            if kg_orch and hasattr(kg_orch, "load_graph"):
                kg_orch.load_graph()
        except Exception as e:
            logger.warning("Failed to restore Knowledge Graph state: %s", e)

        # 10. Load Scheduler
        logger.info("Activating execution scheduler...")
        try:
            sched = container.resolve("StrategySchedulerOrchestrator")
            if sched and hasattr(sched, "start_scheduler"):
                sched.start_scheduler()
        except Exception as e:
            logger.warning("Failed to activate scheduler: %s", e)

        # 11. Load Active Strategies
        logger.info("Restoring strategy state statuses...")
        try:
            strat_orch = container.resolve("StrategyLifecycleOrchestrator")
            if strat_orch and hasattr(strat_orch, "load_active_strategies"):
                strat_orch.load_active_strategies()
        except Exception as e:
            logger.warning("Failed to restore strategy states: %s", e)

        # 12. Restore Portfolio
        logger.info("Restoring portfolio construction values...")
        try:
            port_orch = container.resolve("PortfolioEngineOrchestrator")
            if port_orch and hasattr(port_orch, "restore_portfolio"):
                port_orch.restore_portfolio()
        except Exception as e:
            logger.warning("Failed to restore portfolio: %s", e)

        # 13. Restore Paper Trading Sessions
        logger.info("Restoring paper trading sandbox sessions...")
        try:
            paper_orch = container.resolve("PaperTradingOrchestrator")
            if paper_orch and hasattr(paper_orch, "restore_sessions"):
                paper_orch.restore_sessions()
        except Exception as e:
            logger.warning("Failed to restore paper trading sessions: %s", e)

        # 14. Connect Market Gateway
        logger.info("Connecting market gateway data streams...")
        try:
            market_orch = container.resolve("PaperMarketOrchestrator")
            if market_orch and hasattr(market_orch, "connect_feed"):
                market_orch.connect_feed()
        except Exception as e:
            logger.warning("Failed to connect market gateway: %s", e)

        logger.info("TOJI System Boot completed successfully.")
        return registry

    def shutdown(self, registry: ServiceRegistry) -> None:
        """Execute teardown procedures in reverse order."""
        logger.info("Executing Continuous Runtime Lifecycle Shutdown...")
        container = registry.get_service("Container")

        # 1. Disconnect Market Feed
        try:
            market_orch = container.resolve("PaperMarketOrchestrator")
            if market_orch and hasattr(market_orch, "disconnect_feed"):
                market_orch.disconnect_feed()
        except Exception:
            pass

        # 2. Stop Scheduler
        try:
            sched = container.resolve("StrategySchedulerOrchestrator")
            if sched and hasattr(sched, "stop_scheduler"):
                sched.stop_scheduler()
        except Exception:
            pass

        # 3. Disconnect Database connection pool
        try:
            db = registry.get_service("Database")
            if db:
                db.disconnect()
        except Exception:
            pass

        logger.info("TOJI System Shutdown completed successfully.")
