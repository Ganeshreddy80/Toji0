"""Trade Journal orchestrator coordinating analytics, AI reviews, and registries logs.
"""

from __future__ import annotations

import logging
import uuid
import time
from datetime import datetime, timezone
from typing import Any, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.trade_journal.interfaces import ITradeJournal
from research_platform.trade_journal.models import (
    DailyJournal,
    TradeJournal,
    TradeScore,
    TradeSnapshot,
    TradeStatistics,
)
from research_platform.trade_journal.repository import TradeJournalRepository
from research_platform.trade_journal.analyzer import TradeAnalyzer
from research_platform.trade_journal.metrics import MetricsCalculator
from research_platform.trade_journal.ai_reviewer import TradeReviewer
from research_platform.trade_journal.events import (
    TradeJournalCreated,
    TradeReviewed,
    TradeLessonLearned,
    TradeStatisticsUpdated,
)

logger = logging.getLogger(__name__)


class TradeJournalOrchestrator(ITradeJournal):
    """Central orchestrator managing post-trade analytics and AI evaluations."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = TradeJournalRepository()

        # Helper engine instances
        self._analyzer = TradeAnalyzer()
        self._metrics = MetricsCalculator()
        self._reviewer = TradeReviewer(container)
        
        # Subscriptions tracking
        self._subscribed = False

    @property
    def repository(self) -> TradeJournalRepository:
        return self._repo

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("TradeJournal: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_oms_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.oms.oms_core.OmsCore")

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── Domain Events Subscriptions ──────────────────────────────────

    def start_journaling(self) -> None:
        """Start listening to Event Bus OMS order changes."""
        self._event_bus.subscribe("system.oms_order_state_changed", self._handle_oms_event)
        self._event_bus.subscribe("system.o_m_s_order_state_changed", self._handle_oms_event)
        self._subscribed = True
        logger.info("Trade Journal: Subscribed to OMS state changed events.")

    def stop_journaling(self) -> None:
        """Unsubscribe from the event stream."""
        if self._subscribed:
            try:
                self._event_bus.unsubscribe("system.oms_order_state_changed", self._handle_oms_event)
            except Exception as e:
                logger.error("Trade Journal: Failed to unsubscribe: %s", e)
            try:
                self._event_bus.unsubscribe("system.o_m_s_order_state_changed", self._handle_oms_event)
            except Exception as e:
                logger.error("Trade Journal: Failed to unsubscribe o_m_s: %s", e)
            self._subscribed = False
        logger.info("Trade Journal: Stopped journaling subscription.")

    def _handle_oms_event(self, event: Any) -> None:
        payload = getattr(event, "payload", {}) or {}
        order_id = payload.get("order_id")
        status = payload.get("status")

        # Compile journal when an order successfully executes to FILLED status
        if order_id and status == "FILLED":
            try:
                self.record_completed_trade(order_id)
            except Exception as e:
                logger.error("Trade Journal: Failed to record completed trade for %s: %s", order_id, e)

    # ── ITradeJournal Compilation ─────────────────────────────────────

    def record_completed_trade(self, order_id: str) -> TradeJournal:
        """Retrieve execution metrics, compile MFE/MAE, run AI review, and write journal."""
        oms_orch = self._get_oms_orchestrator()
        if not oms_orch:
            raise RuntimeError("OmsCore orchestrator not found in DI container.")

        order = oms_orch.repository.get_order(order_id)
        if not order:
            raise ValueError(f"Order '{order_id}' not found in OMS repository.")

        # Compute transaction details
        entry_price = order.executed_price if order.executed_price else order.price
        exit_price = entry_price * 1.02 if order.side == "BUY" else entry_price * 0.98  # Mock exit price
        entry_time = order.timestamp
        exit_time = datetime.now(timezone.utc)
        
        commission = self._analyzer.calculate_commission(entry_price, order.quantity)
        slippage = self._analyzer.calculate_slippage(order.price, entry_price, order.quantity)
        holding_time = self._analyzer.calculate_holding_time(entry_time, exit_time)
        
        # PnL logic
        raw_pnl = order.quantity * (exit_price - entry_price) if order.side == "BUY" else order.quantity * (entry_price - exit_price)
        pnl = raw_pnl - commission - slippage

        mfe, mae = self._analyzer.estimate_excursions(entry_price, exit_price, order.quantity, order.side, pnl)

        # Standard score metrics card
        score = TradeScore(
            execution_score=95.0 if slippage == 0.0 else 85.0,
            risk_score=90.0 if pnl > 0.0 else 75.0,
            total_score=92.5 if pnl > 0.0 else 80.0
        )

        # Create basic journal skeleton
        journal_id = f"jrnl-{uuid.uuid4().hex[:8]}"
        temp_journal = TradeJournal(
            journal_id=journal_id,
            order_id=order_id,
            strategy_id=order.strategy_id,
            symbol=order.symbol,
            quantity=order.quantity,
            side=order.side,
            entry_price=entry_price,
            exit_price=exit_price,
            entry_time=entry_time,
            exit_time=exit_time,
            pnl=pnl,
            commission=commission,
            slippage=slippage,
            holding_time_sec=holding_time,
            mfe=mfe,
            mae=mae,
            market_regime="NORMAL",
            score=score,
            review=None,  # Will update post AI evaluation
            tags=[order.side, order.symbol]
        )

        # AI reviews the completed trade details
        review = self._reviewer.generate_review(temp_journal)
        
        journal = temp_journal.model_copy(update={"review": review})
        self._repo.save_journal(journal)

        # Log completed trade details into the long-term TradeMemoryEngine
        try:
            from research_platform.trade_memory.engine import TradeMemoryEngine
            memory_engine = None
            if self._container and self._container.has("TradeMemoryEngine"):
                memory_engine = self._container.resolve("TradeMemoryEngine")
            if memory_engine is None:
                memory_engine = TradeMemoryEngine()
            
            features_dict = {}

            # FP-4 / ADR-001 / OQ-1 Option A: ATR from PriceActionOrchestrator — canonical
            # execution-time ATR must match what ai_signal and confluence used at trade entry.
            pa_atr_val = 0.0
            pa_orch_tj = self._resolve("PriceActionOrchestrator")
            if pa_orch_tj:
                try:
                    pa_atr_val = pa_orch_tj.get_atr(order.symbol)
                except Exception as e:
                    logger.debug("TradeJournal: error fetching PA ATR for trade memory: %s", e)

            feature_platform = self._resolve("FeaturePlatformOrchestrator") or self._resolve("research_platform.feature_platform.orchestrator.FeaturePlatformOrchestrator")
            if feature_platform:
                latest_df = feature_platform.query_realtime([
                    "rsi", "ema9", "ema21", "ema50", "trend", "support", "resistance", "breakout", "volume_change"
                ], [order.symbol])
                if not latest_df.empty:
                    feat_row = latest_df.iloc[-1].to_dict()
                    features_dict = {
                        "RSI": feat_row.get("rsi", 50.0),
                        "rsi": feat_row.get("rsi", 50.0),
                        "trend": feat_row.get("trend", "bullish"),
                        "support": feat_row.get("support", 0.0),
                        "resistance": feat_row.get("resistance", 0.0),
                        "ATR": pa_atr_val,   # canonical PA-ATR (ADR-001)
                        "atr": pa_atr_val,   # canonical PA-ATR (ADR-001)
                        "breakout": feat_row.get("breakout", "none"),
                        "volume_change": feat_row.get("volume_change", 0.0),
                        "close": feat_row.get("close", entry_price),
                        "ema50": feat_row.get("ema50", 0.0)
                    }
            
            memory_engine.save_trade(
                symbol=order.symbol,
                entry=entry_price,
                exit=exit_price,
                entry_time=entry_time,
                exit_time=exit_time,
                features_at_entry=features_dict,
                decision_reason=getattr(order, "rationale", "") or "Signal Confluence",
                pnl=pnl,
                stop_loss=0.0
            )
        except Exception as tm_err:
            logger.error("TradeJournal: Failed to log completed trade into memory engine: %s", tm_err)

        # Recalculate portfolio statistics
        journals = self._repo.list_journals()
        stats = self._metrics.calculate_statistics(journals)
        self._repo.save_statistics(stats)

        # Daily journal aggregation compilation
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily = DailyJournal(
            date=date_str,
            snapshot=TradeSnapshot(
                total_pnl=sum(j.pnl for j in journals),
                total_trades_count=len(journals),
                best_strategy=order.strategy_id,
                worst_strategy=order.strategy_id,
                largest_winner=max(j.pnl for j in journals),
                largest_loser=min(j.pnl for j in journals)
            ),
            journals=journals
        )
        self._repo.save_daily_journal(daily)

        # Broadcast events
        self._event_bus.publish(TradeJournalCreated(payload={"journal_id": journal_id}))
        self._event_bus.publish(TradeReviewed(payload={"journal_id": journal_id, "review_id": review.review_id}))
        self._event_bus.publish(TradeStatisticsUpdated(payload={"expectancy": stats.expectancy}))

        # Downstream logging updates
        self._log_downstream_registries(journal)

        return journal

    def _log_downstream_registries(self, journal: TradeJournal) -> None:
        # 1. Institutional Memory (R16)
        mem_orch = self._get_memory_orchestrator()
        if mem_orch:
            try:
                mem_orch.publish_memory("trade_reviews", {
                    "journal_id": journal.journal_id,
                    "review_summary": journal.review.summary,
                    "lessons_learned": [les.description for les in journal.review.lessons]
                })
                for les in journal.review.lessons:
                    self._event_bus.publish(TradeLessonLearned(payload={"lesson_id": les.lesson_id}))
            except Exception as e:
                logger.error("TradeJournal Audit: Failed to write to institutional memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg_orch = self._get_kg_orchestrator()
        if kg_orch:
            try:
                # Create TRADE node
                kg_orch.register_node(
                    node_id=journal.journal_id,
                    node_type="TRADE",
                    subsystem="trade_journal",
                    event="TradeJournalCreated",
                    author="trade_journal",
                    properties={"pnl": journal.pnl, "symbol": journal.symbol}
                )
                # Create LESSON nodes
                for les in journal.review.lessons:
                    kg_orch.register_node(
                        node_id=les.lesson_id,
                        node_type="LESSON",
                        subsystem="trade_journal",
                        event="TradeLessonLearned",
                        author="trade_journal",
                        properties={"description": les.description}
                    )
            except Exception as e:
                logger.error("TradeJournal Audit: Failed to write to knowledge graph: %s", e)

        # 3. Operations Center Refresh (R30.5)
        ops_orch = self._get_ops_orchestrator()
        if ops_orch:
            try:
                ops_orch.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("TradeJournal: Failed to refresh operations center: %s", e)
