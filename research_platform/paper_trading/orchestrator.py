"""Paper trading orchestrator managing virtual accounts, order executions, and downstream registries.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.paper_trading.interfaces import IPaperTradingOrchestrator
from research_platform.paper_trading.models import (
    PaperAccount,
    PaperExecutionSession,
    PaperOrder,
    PaperPosition,
    TradeJournalEntry,
)
from research_platform.paper_trading.repository import PaperTradingRepository
from research_platform.paper_trading.paper_exchange import PaperExchange
from research_platform.paper_trading.broker_adapter import PaperBrokerAdapter
from research_platform.paper_trading.account import AccountManager
from research_platform.paper_trading.order_tracker import OrderTracker
from research_platform.paper_trading.position_tracker import PositionTracker
from research_platform.paper_trading.pnl_tracker import PnlTracker
from research_platform.paper_trading.portfolio_tracker import PortfolioTracker
from research_platform.paper_trading.trade_journal import TradeJournal
from research_platform.paper_trading.execution_monitor import ExecutionMonitor
from research_platform.paper_trading.session_manager import SessionManager
from research_platform.paper_trading.events import (
    PaperOrderCancelled,
    PaperOrderFilled,
    PaperOrderMatched,
    PaperOrderSubmitted,
    PaperSessionStarted,
    PaperSessionStopped,
)

logger = logging.getLogger(__name__)


class PaperTradingOrchestrator(IPaperTradingOrchestrator):
    """Central orchestrator for TOJI Institutional Paper Trading Foundation."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = PaperTradingRepository()

        # Engine instances
        self._exchange = PaperExchange()
        self._broker = PaperBrokerAdapter(self._exchange)
        self._account_mgr = AccountManager()
        self._order_tracker = OrderTracker()
        self._position_tracker = PositionTracker()
        self._pnl_tracker = PnlTracker()
        self._portfolio_tracker = PortfolioTracker()
        self._journal = TradeJournal()
        self._monitor = ExecutionMonitor()
        self._session_mgr = SessionManager()

        # Active session
        self._active_session: Optional[PaperExecutionSession] = None

    @property
    def repository(self) -> PaperTradingRepository:
        return self._repo

    @property
    def active_session(self) -> Optional[PaperExecutionSession]:
        return self._active_session

    # ── Downstream Integration Helpers ───────────────────────────────

    def _get_memory_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator"):
            return self._container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
        return None

    def _get_kg_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator"):
            return self._container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
        return None

    def _publish_memory_record(self, category: str, record: Any) -> None:
        mem_orch = self._get_memory_orchestrator()
        if not mem_orch:
            return
        try:
            mem_orch.publish_memory(category, record)
        except Exception as e:
            logger.error("Failed to publish to institutional memory: %s", e)

    def _update_knowledge_graph(self, request_node_id: str, label: str, properties: dict) -> None:
        kg_orch = self._get_kg_orchestrator()
        if not kg_orch:
            return
        try:
            kg_orch.register_node(
                node_id=request_node_id,
                node_type=label,
                subsystem="paper_trading",
                event="PaperOrderMatched",
                author="system",
                properties=properties
            )
        except Exception as e:
            logger.error("Failed to update knowledge graph: %s", e)

    # ── Orchestrator Actions ──────────────────────────────────────────

    def start_paper_session(self, account_id: str, initial_balance: float) -> PaperExecutionSession:
        """Start a paper trading execution session."""
        account = PaperAccount(
            account_id=account_id,
            initial_balance=initial_balance,
            cash=initial_balance,
            equity=initial_balance
        )
        self._repo.save_account(account)

        session = self._session_mgr.start_session(account)
        self._active_session = session

        self._event_bus.publish(PaperSessionStarted(payload={"session_id": session.session_id}))
        self._publish_memory_record("paper_sessions", session)

        # KG Update
        self._update_knowledge_graph(session.session_id, "PAPER_SESSION", {"account_id": account_id})

        return session

    def stop_paper_session(self) -> Optional[PaperExecutionSession]:
        """Stop the currently active paper trading session."""
        if not self._active_session:
            return None

        stopped = self._session_mgr.stop_session(self._active_session)
        self._active_session = None

        self._event_bus.publish(PaperSessionStopped(payload={"session_id": stopped.session_id}))
        return stopped

    def submit_paper_order(
        self,
        strategy_id: str,
        symbol: str,
        quantity: float,
        price: float,
        order_type: str,
        side: str,
        rationale: str
    ) -> PaperOrder:
        """Submit a paper order, match it against mock pricing, and update balances/positions."""
        if not self._active_session:
            raise RuntimeError("No active paper execution session running.")

        order_id = f"pord-{uuid.uuid4().hex[:8]}"
        order = PaperOrder(
            order_id=order_id,
            strategy_id=strategy_id,
            symbol=symbol,
            quantity=quantity,
            price=price,
            order_type=order_type,
            side=side
        )

        self._repo.save_order(order)
        self._order_tracker.track_order(order)
        self._event_bus.publish(PaperOrderSubmitted(payload={"order_id": order_id}))

        t_sub = time.perf_counter()

        # Execute through broker adapter mock fills
        filled_order = self._broker.execute_order(self._active_session.account, order)
        self._repo.save_order(filled_order)
        self._order_tracker.track_order(filled_order)

        self._monitor.record_latency(order_id, t_sub)

        if filled_order.status == "FILLED":
            # Real commission fee mock = 0.05%
            commission = filled_order.executed_price * filled_order.quantity * 0.0005
            
            # Update Account Cash/Equity
            updated_account = self._account_mgr.update_balance_on_fill(
                account=self._active_session.account,
                quantity=filled_order.quantity,
                price=filled_order.executed_price,
                side=filled_order.side,
                commission=commission
            )
            self._repo.save_account(updated_account)
            self._active_session = self._active_session.model_copy(update={"account": updated_account})

            # Update Positions Exposure
            pos = self._position_tracker.update_position_on_fill(
                symbol=symbol,
                quantity=filled_order.quantity,
                price=filled_order.executed_price,
                side=filled_order.side
            )
            self._repo.save_position(pos)

            # Log Trade Journal
            entry = self._journal.log_trade(
                symbol=symbol,
                quantity=filled_order.quantity,
                price=filled_order.executed_price,
                side=filled_order.side,
                rationale=rationale
            )
            self._repo.save_journal(entry)

            # Publish Fill Event
            self._event_bus.publish(PaperOrderFilled(payload={
                "order_id": order_id,
                "price": filled_order.executed_price,
                "symbol": symbol,
                "side": filled_order.side,
                "quantity": filled_order.quantity,
                "strategy": strategy_id,
                "rationale": rationale,
                "ai_confidence": 0.8
            }))

            # Downstream Memory and Graph logs updates
            self._publish_memory_record("paper_trades", filled_order)
            self._publish_memory_record("trade_journals", entry)
            self._update_knowledge_graph(order_id, "PAPER_ORDER", {"symbol": symbol, "status": "FILLED"})

        return filled_order

    def update_market_price(self, symbol: str, price: float) -> None:
        """Process price feed updates to update unrealized returns and peak drawdowns."""
        if not self._active_session:
            return

        positions = self._repo.list_positions()
        current_prices = {symbol: price}

        # Calculate unrealized gains
        updated_positions = self._pnl_tracker.update_unrealized_pnl(positions, current_prices)
        for pos in updated_positions:
            self._repo.save_position(pos)

        # Compute gross positions value
        open_val = sum(pos.quantity * pos.current_price for pos in updated_positions)

        # Update Portfolio equity and drawdown
        updated_account = self._portfolio_tracker.calculate_drawdown(
            account=self._active_session.account,
            open_positions_val=open_val
        )
        self._repo.save_account(updated_account)
        self._active_session = self._active_session.model_copy(update={"account": updated_account})
