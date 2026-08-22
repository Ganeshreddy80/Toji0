"""Trade Manager dispatching trades to OMS and EMS layers.

Routing logic:
  TRADING_MODE=paper  →  PaperExecutionRouter  →  PaperTradingOrchestrator
  TRADING_MODE=live   →  ExecutionEngineOrchestrator (real exchange)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from research_platform.oms.models import OrderRequest
from research_platform.oms.orchestrator import OrderManagementSystemOrchestrator
from research_platform.execution_engine.orchestrator import ExecutionEngineOrchestrator

logger = logging.getLogger(__name__)


class TradeManager:
    """Dispatches trades, linking OMS ingestion and EMS/Paper execution steps."""

    def __init__(
        self,
        oms: OrderManagementSystemOrchestrator,
        ems: ExecutionEngineOrchestrator,
        paper_router: Optional[object] = None,
    ) -> None:
        self.oms = oms
        self.ems = ems
        self._paper_router = paper_router  # PaperExecutionRouter instance (injected when TRADING_MODE=paper)

    def execute_signal_trade(
        self,
        order_id: str,
        symbol: str,
        direction: str,
        quantity: float,
        price: float
    ) -> bool:
        """Process signal ingestion, order validation, and execution routing.

        In PAPER mode the order is routed to PaperExecutionRouter which forwards it
        to PaperTradingOrchestrator for simulated fills.
        In LIVE mode the order is routed to ExecutionEngineOrchestrator.
        """
        trading_mode = os.getenv("TRADING_MODE", "paper").lower()

        req = OrderRequest(
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            order_type="MARKET" if os.getenv("TRADING_MODE") == "paper" else "LIMIT",
            price=price
        )

        try:
            # 1. OMS Ingestion — always runs regardless of mode
            routed = self.oms.ingest_order(req)

            if trading_mode == "paper":
                # If the order is already in a terminal state (FILLED/CANCELLED/REJECTED),
                # do not execute a duplicate routing pass.
                if routed.status in ("FILLED", "CANCELLED", "REJECTED"):
                    logger.info("TradeManager [PAPER]: order %s already executed by OMS: %s", order_id, routed.status)
                    return routed.status == "FILLED"

                # 2a. Paper Mode — route through PaperExecutionRouter
                if self._paper_router is None:
                    logger.error(
                        "TradeManager: TRADING_MODE=paper but no PaperExecutionRouter injected. "
                        "Order %s dropped.", order_id
                    )
                    return False

                result = self._paper_router.route_order(
                    strategy_id=order_id,
                    symbol=symbol,
                    quantity=quantity,
                    price=price,
                    order_type="MARKET",
                    side=direction,
                    rationale="signal_trade"
                )
                status = getattr(result, "status", None) or (result.get("status") if isinstance(result, dict) else None)
                logger.info("TradeManager [PAPER]: order %s → %s", order_id, status)
                return status == "FILLED"
            else:
                # 2b. Live Mode — route through real ExecutionEngineOrchestrator
                report = self.ems.execute_order(routed, exchange="BINANCE")
                logger.info("TradeManager [LIVE]: executed trade: %s", report.status)
                return report.status == "FILLED"

        except Exception as e:
            logger.error("TradeManager failed execution (mode=%s): %s", trading_mode, e)
            return False
