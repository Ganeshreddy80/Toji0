"""Production Validation Sprint 1 E2E Pipeline Validation Script.
"""

from __future__ import annotations

import os
import sys
import time
import logging
from datetime import datetime, timezone
import uuid

# Programmatically append project root to sys.path to resolve imports cleanly without PYTHONPATH env var
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Force DEV mode to run in-memory SQLite and disable Telegram/Redis production alerts
os.environ["DATABASE_MODE"] = "DEV"
os.environ["TOJI_MODE"] = "DEV"
os.environ["TOJI_VALIDATION_MODE"] = "true"
os.environ["MARKET_PROVIDER"] = "demo"

# Set up logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Sprint_Validation")

from research_platform.platform.bootstrap import bootstrap_platform
from research_platform.platform.service_registry import ServiceRegistry
from toji_platform.core.event_bus.events import MarketDataReceived
from toji_platform.runtime.state import RuntimeStateManager


def main() -> int:
    logger.info("Initializing Sprint 1 validation boot...")
    app = bootstrap_platform()
    container = ServiceRegistry().get_service("Container")
    event_bus = ServiceRegistry().get_service("EventBus")

    state_manager = RuntimeStateManager()
    state_manager.load()

    # Verify that the required services are registered in the DI Container
    required_services = [
        "PriceActionOrchestrator",
        "FeaturePlatformOrchestrator",
        "AISignalGenerator",
        "PortfolioGovernor",
        "PositionSizingOrchestrator",
        "OrderManagementSystemOrchestrator",
        "ExecutionEngineOrchestrator",
        "PaperExecutionRouter",
        "AccountingService",
        "PerformanceEngine",
        "LedgerRepository",
    ]
    
    logger.info("--- Stage 0: DI Container Service Registrations Validation ---")
    for svc in required_services:
        has_svc = container.has(svc)
        logger.info("DI Service '%s': %s", svc, "RESOLVED ✓" if has_svc else "FAILED ✗")
        if not has_svc:
            logger.error("Critical service '%s' is missing in container!", svc)
            app.shutdown()
            return 1

    # Get services
    pa = container.resolve("PriceActionOrchestrator")
    fp = container.resolve("FeaturePlatformOrchestrator")
    ai = container.resolve("AISignalGenerator")
    gov = container.resolve("PortfolioGovernor")
    sizer = container.resolve("PositionSizingOrchestrator")
    oms = container.resolve("OrderManagementSystemOrchestrator")
    router = container.resolve("PaperExecutionRouter")
    accounting = container.resolve("AccountingService")

    # Hook listener to capture system.paper_order_filled events (Single-event guarantee verification)
    paper_order_filled_events = []
    def on_paper_order_filled(event) -> None:
        paper_order_filled_events.append(event)
        logger.info("[VAL_EVENT] Captured system.paper_order_filled event: %s", event)

    event_bus.subscribe("system.paper_order_filled", on_paper_order_filled)

    logger.info("--- Stage 1 & 2: Market Gateway & Feature Platform Integration Check ---")
    
    # We will publish 25 ticks to build up EMA9, EMA21, ATR, and support/resistance features.
    start_price = 50000.0
    tick_time = datetime.now(timezone.utc)
    for i in range(25):
        # We walk the price down to simulate a bearish move, then up to trigger confluence
        if i < 15:
            price = start_price - (i * 200.0)  # down from 50k to 47k
        else:
            price = start_price - (15 * 200.0) + ((i - 15) * 600.0)  # up from 47k to 53k
        
        logger.info("Tick %d: Symbol=BTCUSDT, Price=%.2f", i + 1, price)
        event = MarketDataReceived(
            source="BinanceDemoGateway",
            payload={
                "symbol": "BTCUSDT",
                "price": price,
                "timestamp": tick_time.isoformat(),
                "volume": 2.5
            }
        )
        event_bus.publish(event)
        time.sleep(0.01)

    state_manager.load()
    logger.info("State ticks_processed: %d", state_manager.processed_ticks)
    logger.info("State features_generated: %d", state_manager.features_generated)
    logger.info("State strategy decisions: BUY=%d, SELL=%d, HOLD=%d",
                state_manager.strategy_buy, state_manager.strategy_sell, state_manager.strategy_hold)
    logger.info("State AI Audits: Approved=%d, Rejected=%d", state_manager.ai_approved, state_manager.ai_rejected)
    logger.info("State Risk Audits: Approved=%d, Rejected=%d", state_manager.risk_approved, state_manager.risk_rejected)
    logger.info("State OMS Orders Created: %d", state_manager.orders_created)
    logger.info("State Executed Trades/Fills: %d", state_manager.trades_filled)

    # Fetch status summary from the accounting service
    summary = accounting.get_portfolio_summary()
    logger.info("--- Portfolio Accounting Summary ---")
    logger.info("Cash: %.2f", summary["cash"])
    logger.info("Equity: %.2f", summary["equity"])
    logger.info("Realized PnL: %.2f", summary["realized_pnl"])
    logger.info("Unrealized PnL: %.2f", summary["unrealized_pnl"])
    logger.info("Open Positions: %d", summary["open_positions"])
    logger.info("Position List: %s", summary["positions"])
    logger.info("Peak Equity: %.2f", summary["peak_equity"])
    logger.info("Drawdown: %.4f%%", summary["drawdown"])
    logger.info("Win Rate: %.2f%%", summary["win_rate"] * 100.0)
    logger.info("Profit Factor: %.2f", summary["profit_factor"])
    logger.info("Ledger Entry Count: %d", len(accounting.ledger_repository.get_all()))

    # --- Stage 3: Consistency & Regression Proofs ---
    logger.info("--- Stage 3: Consistency & Regression Proofs ---")
    db = ServiceRegistry().get_service("Database")
    if not db:
        logger.error("FAILURE: Database service is missing in container! ✗")
        app.shutdown()
        return 3

    from research_platform.persistence.postgres.session import DatabaseSessionManager
    from research_platform.persistence.repositories.trade_repository import PostgresTradeRepository
    from research_platform.persistence.repositories.ledger_repository import PostgresLedgerRepository

    session_mgr = DatabaseSessionManager(db)
    trade_repo = PostgresTradeRepository(session_mgr)
    ledger_repo = PostgresLedgerRepository(session_mgr)

    db_orders = oms.repository.list_orders()
    db_trades = trade_repo.list_trades()
    db_ledger = ledger_repo.list_entries()

    logger.info("Captured paper_order_filled events: %d", len(paper_order_filled_events))
    logger.info("State Manager Trades filled: %d", state_manager.trades_filled)
    logger.info("Database Trades row count: %d", len(db_trades))
    logger.info("Database Ledger row count: %d", len(db_ledger))
    logger.info("Database Orders row count: %d", len(db_orders))

    # Verification 1: Single-event guarantee (Exactly one paper_order_filled event per filled trade)
    if len(paper_order_filled_events) != state_manager.trades_filled:
        logger.error("FAILURE: Single-event guarantee violated! Events (%d) != Runtime trades (%d) ✗",
                     len(paper_order_filled_events), state_manager.trades_filled)
        app.shutdown()
        return 4
    logger.info("Single-event guarantee PROVED (exactly 1 event per trade) ✓")

    # Verification 2: Runtime vs Database consistency
    if not (state_manager.trades_filled == len(db_trades) == len(db_ledger)):
        logger.error("FAILURE: Runtime-vs-database inconsistency detected! State (%d) != DB Trades (%d) != DB Ledger (%d) ✗",
                     state_manager.trades_filled, len(db_trades), len(db_ledger))
        app.shutdown()
        return 5
    logger.info("Runtime-vs-database consistency PROVED ✓")

    # Verification 3: OMS Status transitions
    filled_orders = [o for o in db_orders if o.status == "FILLED"]
    logger.info("Database Orders status: FILLED=%d, total=%d", len(filled_orders), len(db_orders))
    if len(filled_orders) != state_manager.trades_filled:
        logger.error("FAILURE: OMS status transition failed! FILLED orders in DB (%d) != State Trades (%d) ✗",
                     len(filled_orders), state_manager.trades_filled)
        app.shutdown()
        return 6
    logger.info("OMS status transitions to FILLED PROVED ✓")

    # Verify if at least one trade completed successfully
    if state_manager.trades_filled > 0:
        logger.info("SUCCESS: Full paper trading lifecycle successfully verified with complete consistency proofs! ✓")
        app.shutdown()
        return 0
    else:
        logger.error("FAILURE: Tick pipeline ran but zero trades were completed! ✗")
        app.shutdown()
        return 2


if __name__ == "__main__":
    sys.exit(main())
