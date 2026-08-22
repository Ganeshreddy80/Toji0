"""OMS core manager coordinating validations, risk checks, and execution routing.
"""

from __future__ import annotations

import logging
import uuid
import time
from datetime import datetime, timezone
from typing import Any, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.oms.interfaces import IOMS, IOrderRouter, IExecutionTracker
from research_platform.oms.models import Order, ExecutionReport, Fill, OrderRequest, ParentOrder
from research_platform.oms.order_state_machine import OrderStateMachine
from research_platform.oms.repository import OMSRepository
from research_platform.oms.events import (
    OMSOrderCreated,
    OMSOrderRouted,
    OMSOrderStateChanged,
)


logger = logging.getLogger(__name__)


class OmsCore(IOMS, IOrderRouter, IExecutionTracker):
    """Central Order Management System orchestrator for the TOJI platform."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = OMSRepository()
        self._state_machine = OrderStateMachine()
        
        # Telemetry metrics
        self._latencies: List[float] = []

    @property
    def repository(self) -> OMSRepository:
        return self._repo

    # ── Downstream Resolvers ─────────────────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("OMS: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_risk_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.risk_management.orchestrator.RiskManagementOrchestrator")

    def _get_execution_router(self) -> Optional[Any]:
        # 1. Primary: via PaperMarketOrchestrator (canonical path)
        m_key = "research_platform.paper_market.orchestrator.PaperMarketOrchestrator"
        m_orch = self._resolve(m_key)
        if m_orch and hasattr(m_orch, "execution_router") and m_orch.execution_router is not None:
            return m_orch.execution_router

        # 2. Fallback: directly-registered PaperExecutionRouter (registered by PaperMarketPlugin)
        router = self._resolve("PaperExecutionRouter")
        if router is not None:
            return router

        # 3. Last resort: resolve by class
        try:
            from research_platform.paper_market.paper_execution_router import PaperExecutionRouter
            router = self._resolve(PaperExecutionRouter)
            if router is not None:
                return router
        except Exception:
            pass

        logger.warning("OmsCore: No execution router found. Order will fall through to REJECTED.")
        return None

    # ── Downstream Integrations Logs ─────────────────────────────────

    def _log_audit_transitions(self, order: Order, rationale: str) -> None:
        # 1. Institutional Memory (R16)
        mem_key = "research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator"
        mem_orch = self._resolve(mem_key)
        if mem_orch:
            try:
                mem_orch.publish_memory("oms_orders_audit", {
                    "order_id": order.order_id,
                    "status": order.status,
                    "symbol": order.symbol,
                    "quantity": order.quantity,
                    "timestamp": order.timestamp.isoformat(),
                    "rationale": rationale
                })
            except Exception as e:
                logger.error("OMS Audit: Failed to write to institutional memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg_key = "research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator"
        kg_orch = self._resolve(kg_key)
        if kg_orch:
            try:
                kg_orch.register_node(
                    node_id=order.order_id,
                    node_type="OMS_ORDER",
                    subsystem="oms",
                    event="OMSOrderStateChanged",
                    author="oms_core",
                    properties={"status": order.status, "side": order.side}
                )
            except Exception as e:
                logger.error("OMS Audit: Failed to write to knowledge graph: %s", e)

    # ── IOMS Order Placement Entry ────────────────────────────────────

    def submit_order(
        self,
        strategy_id: str,
        symbol: str,
        quantity: float,
        price: float,
        order_type: str,
        side: str,
        rationale: str,
        order_id: Optional[str] = None,
        request: Optional[OrderRequest] = None
    ) -> Order:
        """Process strategy orders execution, validate parameters, and evaluate risk bounds."""
        if order_id is None:
            order_id = f"ord-{uuid.uuid4().hex[:8]}"
        
        # 1. Create order in NEW status
        order = Order(
            order_id=order_id,
            strategy_id=strategy_id,
            symbol=symbol,
            quantity=quantity,
            price=price,
            order_type=order_type,
            side=side,
            status="NEW",
            request=request
        )
        self._repo.save_order(order)
        self._event_bus.publish(OMSOrderCreated(payload={"order_id": order_id}))
        self._log_audit_transitions(order, rationale)

        t_start = time.perf_counter()

        # 2. Enforce limits checks and duplicates validations
        try:
            self._validate_limits(order)
        except ValueError as e:
            logger.error("OMS Validation Failure: %s", e)
            rejected_order = order.model_copy(update={"status": "REJECTED"})
            self._repo.save_order(rejected_order)
            self._event_bus.publish(OMSOrderStateChanged(payload={"order_id": order_id, "status": "REJECTED"}))
            self._log_audit_transitions(rejected_order, f"Validation Failed: {e}")
            return rejected_order

        validated_order = order.model_copy(update={"status": "VALIDATED"})
        self._repo.save_order(validated_order)
        self._log_audit_transitions(validated_order, "Validation Passed")

        # 3. Call Risk Management evaluation
        risk_orch = self._get_risk_orchestrator()
        if risk_orch:
            # Enforce limits check
            try:
                from research_platform.oms.models import OrderRequest
                req = OrderRequest(
                    order_id=order.order_id,
                    symbol=order.symbol,
                    direction=order.side,
                    quantity=order.quantity,
                    order_type=order.order_type,
                    price=order.price
                )
                report = risk_orch._compliance.evaluate_compliance(req)
                if not report.compliant:
                    raise ValueError(f"Compliance check failed: {'; '.join(report.rejection_reasons)}")
            except Exception as e:
                logger.error("OMS Risk Failure: %s", e)
                rejected_order = validated_order.model_copy(update={"status": "REJECTED"})
                self._repo.save_order(rejected_order)
                self._log_audit_transitions(rejected_order, f"Risk Blocked: {e}")
                return rejected_order

        queued_order = validated_order.model_copy(update={"status": "QUEUED"})
        self._repo.save_order(queued_order)
        self._log_audit_transitions(queued_order, "Order Queued")

        # 4. Route order to Executions Engine
        routed_order = self.route_order(queued_order, rationale)
        
        t_lat = time.perf_counter() - t_start
        self._latencies.append(t_lat)
        
        return routed_order

    def _validate_limits(self, order: Order) -> None:
        if order.quantity <= 0.0:
            raise ValueError("Invalid Quantity: Order quantity must be greater than zero.")
        if not order.symbol:
            raise ValueError("Invalid Symbol: Symbol must not be blank.")
        
        # Duplicates checking: evaluate matching orders placed in the last 5 seconds
        now = datetime.now(timezone.utc)
        recent_orders = self._repo.list_orders()
        for ro in recent_orders:
            if ro.order_id == order.order_id:
                continue
            if ro.status in ("FILLED", "CANCELLED", "REJECTED"):
                continue
            dt = (now - ro.timestamp).total_seconds()
            if dt <= 5.0:
                if (ro.strategy_id == order.strategy_id and
                    ro.symbol == order.symbol and
                    ro.quantity == order.quantity and
                    ro.side == order.side and
                    ro.price == order.price):
                    raise ValueError(f"Duplicate Order Warning: Matching order '{ro.order_id}' submitted recently.")

    # ── IOrderRouter Actions ──────────────────────────────────────────

    def route_order(self, order: Order, rationale: str) -> Order:
        """Send orders to downstream brokers or paper routers."""
        routed_order = order.model_copy(update={"status": "ROUTED"})
        self._repo.save_order(routed_order)
        self._event_bus.publish(OMSOrderRouted(payload={"order_id": order.order_id}))
        self._log_audit_transitions(routed_order, "Routing Order")

        exec_router = self._get_execution_router()
        if exec_router:
            try:
                # Maps order execution to execution router (R29)
                # It returns the filled/matched PaperOrder Pydantic model
                res = exec_router.route_order(
                    strategy_id=order.strategy_id,
                    symbol=order.symbol,
                    quantity=order.quantity,
                    price=order.price,
                    order_type=order.order_type,
                    side=order.side,
                    rationale=rationale
                )
                
                # Check outcome status of matched paper executions
                status = getattr(res, "status", "REJECTED")
                exec_price = getattr(res, "executed_price", order.price)
                exec_qty = getattr(res, "executed_quantity", order.quantity)

                if status == "FILLED":
                    report = ExecutionReport(
                        execution_id=f"exec-{uuid.uuid4().hex[:8]}",
                        order_id=order.order_id,
                        status="FILLED",
                        price=exec_price,
                        quantity=exec_qty
                    )
                    self.handle_execution_report(report)
                    return self._repo.get_order(order.order_id) or routed_order

                elif status == "CANCELLED":
                    cancelled_order = routed_order.model_copy(update={"status": "CANCELLED"})
                    self._repo.save_order(cancelled_order)
                    self._log_audit_transitions(cancelled_order, "Execution Cancelled")
                    return cancelled_order

            except Exception as e:
                logger.error("OMS Router Failure: %s", e)
        else:
            # Check if live mode is active (non-paper) and return routed_order directly
            import os
            if os.getenv("TRADING_MODE", "paper").lower() != "paper":
                logger.info("OmsCore: Live trading mode active. Order returned in ROUTED status for external execution.")
                return routed_order
                
        rejected_order = routed_order.model_copy(update={"status": "REJECTED"})
        self._repo.save_order(rejected_order)
        self._log_audit_transitions(rejected_order, "Execution Rejected")
        return rejected_order

    # ── IExecutionTracker Actions ──────────────────────────────────────

    def handle_execution_report(self, report: ExecutionReport) -> None:
        """Process execution updates, migrating orders states and storing fills."""
        order = self._repo.get_order(report.order_id)
        if not order:
            logger.warning("OMS: Execution report received for untracked order '%s'", report.order_id)
            return

        updated_order = order.model_copy(update={
            "status": report.status,
            "executed_price": report.price,
            "executed_quantity": report.quantity
        })
        self._repo.save_order(updated_order)
        self._event_bus.publish(OMSOrderStateChanged(payload={
            "order_id": order.order_id,
            "status": report.status
        }))
        self._log_audit_transitions(updated_order, f"Execution report processed: {report.status}")

        if report.status == "FILLED":
            fill = Fill(
                fill_id=f"fill-{uuid.uuid4().hex[:8]}",
                order_id=report.order_id,
                price=report.price,
                quantity=report.quantity,
                commission=report.commission
            )
            self._repo.save_fill(fill)

    # ── Metrics Accumulators ──────────────────────────────────────────

    def get_performance_metrics(self) -> dict[str, float]:
        """Aggregate performance telemetry metrics."""
        orders = self._repo.list_orders()
        total = len(orders)
        
        filled = len([o for o in orders if o.status == "FILLED"])
        cancelled = len([o for o in orders if o.status == "CANCELLED"])
        rejected = len([o for o in orders if o.status == "REJECTED"])

        avg_lat = sum(self._latencies) / len(self._latencies) if self._latencies else 0.0

        return {
            "average_execution_time_sec": avg_lat,
            "fill_ratio": filled / total if total > 0 else 0.0,
            "cancel_ratio": cancelled / total if total > 0 else 0.0,
            "reject_ratio": rejected / total if total > 0 else 0.0
        }

    # ── Compat Methods for OrderManagementSystemOrchestrator ─────────

    def ingest_order(self, request: OrderRequest) -> Order:
        """Process and validate strategy orders before execution routing."""
        from research_platform.oms.events import OrderReceived
        self._event_bus.publish(OrderReceived(payload={"order_id": request.order_id}))

        # Manual compliance check (kill switch)
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            container = ServiceRegistry().get_service("Container")
            if container:
                from research_platform.risk_management.orchestrator import RiskManagementOrchestrator
                risk_orch = container.resolve(RiskManagementOrchestrator)
                if risk_orch and risk_orch.kill_switch.is_activated:
                    raise ValueError(f"Compliance validation failed: KillSwitch activated. Reason: {risk_orch.kill_switch.get_status().reason}")
        except ValueError:
            raise
        except Exception:
            pass

        return self.submit_order(
            strategy_id=request.strategy_id,
            symbol=request.symbol,
            quantity=request.quantity,
            price=request.price,
            order_type=request.order_type,
            side=request.direction,
            rationale="signal_trade",
            order_id=request.order_id,
            request=request
        )

    def create_algorithmic_parent(
        self,
        order: Order,
        algo_type: str,
        slices_count: int
    ) -> ParentOrder:
        """Create parent order wrappers and slice child execution partitions."""
        from research_platform.oms.parent_child import ParentChildEngine
        from research_platform.oms.models import ParentOrder
        from research_platform.oms.events import ParentCreated, ChildCreated

        # Validate transition: ROUTED -> PENDING
        pending_order = self._state_machine.transition(order, "PENDING")
        self._repo.save_order(pending_order)

        parent_id = f"parent_{order.order_id}"
        parent = ParentOrder(
            parent_id=parent_id,
            order=pending_order,
            algo_type=algo_type,
            algo_params={"slices_count": slices_count}
        )

        # Slice children
        if algo_type == "TWAP":
            children = ParentChildEngine.slice_twap(parent, slices_count)
        elif algo_type == "ICEBERG":
            children = ParentChildEngine.slice_iceberg(parent, display_qty=parent.order.request.quantity / slices_count)
        else:
            children = ParentChildEngine.slice_twap(parent, slices_count)

        child_ids = [c.child_id for c in children]
        
        # Update parent child links
        updated_parent = ParentOrder(
            parent_id=parent_id,
            order=pending_order,
            algo_type=algo_type,
            algo_params={"slices_count": slices_count},
            child_ids=child_ids
        )

        self._repo.save_parent(updated_parent)
        self._event_bus.publish(ParentCreated(payload={"parent_id": parent_id}))

        for child in children:
            self._repo.save_child(child)
            self._event_bus.publish(ChildCreated(payload={"child_id": child.child_id}))

        logger.info("OMS successfully generated parent %s with %d children.", parent_id, len(children))
        return updated_parent

