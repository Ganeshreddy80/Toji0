"""Portfolio Accounting DI Plugin.

Registers AccountingService, PerformanceEngine, and LedgerRepository, and subscribes to:
  - system.market_data_received   → on_market_tick
  - system.paper_order_matched    → on_fill
  - system.paper_order_filled     → on_fill
  - system.order_filled           → on_fill
  - system.position_closed        → on_position_closed
  - system.position_updated       → on_position_updated
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class PortfolioAccountingPlugin:
    """Boot plugin for the Portfolio Accounting subsystem."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        from research_platform.portfolio_accounting.accounting_service import AccountingService
        from research_platform.portfolio_accounting.performance_engine import PerformanceEngine
        from research_platform.portfolio_accounting.ledger_repository import LedgerRepository

        event_bus = self.container.resolve("IEventBus")
        initial_balance = float(os.getenv("PAPER_INITIAL_BALANCE", "100000.0"))

        service = AccountingService(
            event_bus=event_bus,
            initial_balance=initial_balance,
        )

        # Subscribe to event bus topics
        event_bus.subscribe("system.market_data_received", service.on_market_tick)
        event_bus.subscribe("system.paper_order_matched",  service.on_fill)
        event_bus.subscribe("system.paper_order_filled",   service.on_fill)
        event_bus.subscribe("system.order_filled",         service.on_fill)
        event_bus.subscribe("system.position_closed",      service.on_position_closed)
        event_bus.subscribe("system.position_updated",     service.on_position_updated)

        logger.info(
            "PortfolioAccountingPlugin: initialized (balance=%.2f) — "
            "subscribed to market_data_received, fills, and position events.",
            initial_balance,
        )

        # Register in the DI container
        self.container.register(AccountingService, instance=service)
        self.container.register("AccountingService",   instance=service)
        self.container.register("PortfolioAccounting", instance=service)

        # Register PerformanceEngine and LedgerRepository
        self.container.register(PerformanceEngine, instance=service.metrics_engine)
        self.container.register("PerformanceEngine", instance=service.metrics_engine)
        self.container.register(LedgerRepository, instance=service.ledger_repository)
        self.container.register("LedgerRepository", instance=service.ledger_repository)

        # Attempt authoritative state rehydration from PostgreSQL
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            db = ServiceRegistry().get_service("Database")
            if db:
                service.rehydrate_from_db(db)
        except Exception as e:
            logger.error("PortfolioAccountingPlugin: failed to rehydrate portfolio state: %s", e)
            mode = os.getenv("DATABASE_MODE", os.getenv("TOJI_MODE", "PAPER")).upper()
            if mode != "DEV":
                raise

