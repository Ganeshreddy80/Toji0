"""Execution Management System Engine.

The EMS Engine is the central orchestrator that:
1. Receives approved OrderIntents from the OMS.
2. Selects the correct execution algorithm based on intent.algorithm.
3. Generates child order slices via the algorithm.
4. Executes slices against the broker adapter.
5. Tracks algorithmic progress and emits events.
6. Returns the final ExecutionResult to the OMS.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from execution_engine.brokers.broker_interface import IBrokerAdapter
from execution_engine.brokers.broker_router import BrokerRouter
from execution_engine.core.audit import ExecutionAuditRecord
from execution_engine.core.enums import (
    ExecutionAlgorithmType,
    ExecutionStatus,
    OrderState,
    OrderType,
)
from execution_engine.core.events import (
    ExecutionAlgorithmCompleted,
    ExecutionAlgorithmProgress,
    ExecutionAlgorithmStarted,
    ExecutionCompleted,
    OrderSliceSubmitted,
)
from execution_engine.core.models import (
    ExecutionAlgorithmState,
    ExecutionResult,
    ExecutionSlice,
    Order,
    OrderFill,
    OrderIntent,
)
from execution_engine.ems.base import BaseExecutionAlgorithm
from execution_engine.ems.bracket import BracketAlgorithm
from execution_engine.ems.iceberg import IcebergAlgorithm
from execution_engine.ems.oco import OcoAlgorithm
from execution_engine.ems.pov import PovAlgorithm
from execution_engine.ems.twap import TwapAlgorithm
from execution_engine.ems.vwap import VwapAlgorithm

logger = logging.getLogger(__name__)


class DirectAlgorithm(BaseExecutionAlgorithm):
    """Direct execution: single order, no slicing."""

    def __init__(self) -> None:
        super().__init__(ExecutionAlgorithmType.DIRECT)

    def generate_slices(
        self,
        intent: OrderIntent,
        adapter: IBrokerAdapter,
    ) -> List[ExecutionSlice]:
        return [ExecutionSlice(
            slice_id=f"direct-{uuid.uuid4().hex[:8]}",
            algo_id=f"direct-{intent.intent_id}",
            intent_id=intent.intent_id,
            execution_id=intent.execution_id,
            slice_index=0,
            quantity=intent.quantity,
            price=intent.price,
        )]

    def execute(
        self,
        intent: OrderIntent,
        slices: List[ExecutionSlice],
        adapter: IBrokerAdapter,
    ) -> ExecutionResult:
        orders: List[Order] = []
        fills: List[OrderFill] = []

        for s in slices:
            child_order = self.create_child_order(intent, s)
            try:
                executed = adapter.submit_order(child_order)
                orders.append(executed)

                if executed.state in (OrderState.FILLED, OrderState.PARTIALLY_FILLED):
                    adapter_fills = getattr(adapter, "_fills_log", [])
                    matched = [f for f in adapter_fills if f.client_order_id == child_order.client_order_id]
                    fills.extend(matched)
            except Exception as e:
                logger.error("Direct: Order failed for %s: %s", intent.symbol, e)
                failed = child_order.model_copy(update={
                    "state": OrderState.REJECTED,
                    "error_message": str(e),
                    "updated_at": datetime.now(timezone.utc),
                })
                orders.append(failed)

        has_fill = any(o.state in (OrderState.FILLED, OrderState.PARTIALLY_FILLED) for o in orders)
        status = ExecutionStatus.EXECUTED if has_fill else ExecutionStatus.FAILED
        return self.build_execution_result(intent, orders, fills, status)


class EmsEngine:
    """Execution Management System Engine.

    Routes approved intents to the correct execution algorithm,
    manages algorithmic state tracking, and returns execution results.
    """

    def __init__(
        self,
        broker_router: BrokerRouter,
        event_bus: Any = None,
        execution_repository: Any = None,
    ) -> None:
        self._broker_router = broker_router
        self._event_bus = event_bus
        self._execution_repository = execution_repository
        self._lock = threading.Lock()

        # Algorithm registry
        self._algorithms: Dict[ExecutionAlgorithmType, BaseExecutionAlgorithm] = {
            ExecutionAlgorithmType.DIRECT: DirectAlgorithm(),
            ExecutionAlgorithmType.TWAP: TwapAlgorithm(),
            ExecutionAlgorithmType.VWAP: VwapAlgorithm(),
            ExecutionAlgorithmType.ICEBERG: IcebergAlgorithm(),
            ExecutionAlgorithmType.POV: PovAlgorithm(),
            ExecutionAlgorithmType.BRACKET: BracketAlgorithm(),
            ExecutionAlgorithmType.OCO: OcoAlgorithm(),
        }

        # Active algorithm state tracking
        self._algo_states: Dict[str, ExecutionAlgorithmState] = {}

    def execute_intent(self, intent: OrderIntent, broker_id: str) -> ExecutionResult:
        """Execute an approved intent through the appropriate algorithm.

        Args:
            intent: The approved OrderIntent from the OMS.
            broker_id: The target broker adapter identifier.

        Returns:
            ExecutionResult summarising the execution outcome.
        """
        algo_type = intent.algorithm
        algorithm = self._algorithms.get(algo_type)
        if algorithm is None:
            logger.error("EMS: Unknown algorithm type: %s", algo_type.value)
            return ExecutionResult(
                execution_id=intent.execution_id,
                request_id=intent.request_id,
                correlation_id=intent.correlation_id,
                status=ExecutionStatus.FAILED,
                timestamp=datetime.now(timezone.utc),
            )

        # Resolve broker adapter
        adapter = self._broker_router.get_adapter(broker_id)

        logger.info(
            "EMS: Executing intent %s via %s algorithm on broker %s.",
            intent.intent_id, algo_type.value, broker_id,
        )

        # Emit algorithm started event
        self._emit_event(ExecutionAlgorithmStarted, intent, {
            "algorithm": algo_type.value,
            "broker_id": broker_id,
        })

        # Generate slices
        slices = algorithm.generate_slices(intent, adapter)

        # Build initial algo state
        algo_state = algorithm.build_algo_state(intent, slices)
        with self._lock:
            self._algo_states[intent.intent_id] = algo_state

        # Write audit record
        if self._execution_repository:
            record = ExecutionAuditRecord(
                execution_id=intent.execution_id,
                correlation_id=intent.correlation_id,
                actor="ems_engine",
                action="ALGORITHM_START",
                before={"state": "ROUTED"},
                after={
                    "algorithm": algo_type.value,
                    "slices": len(slices),
                    "broker_id": broker_id,
                },
                reason=f"EMS executing {algo_type.value} with {len(slices)} slices.",
            )
            self._execution_repository.save_audit_record(record)

        # Execute the algorithm
        try:
            result = algorithm.execute(intent, slices, adapter)
        except Exception as e:
            logger.error("EMS: Algorithm execution failed for %s: %s", intent.intent_id, e)
            result = ExecutionResult(
                execution_id=intent.execution_id,
                request_id=intent.request_id,
                correlation_id=intent.correlation_id,
                status=ExecutionStatus.FAILED,
                timestamp=datetime.now(timezone.utc),
            )

        # Update final algo state
        filled_qty = sum(
            o.filled_quantity or 0.0
            for o in result.orders
            if o.state in (OrderState.FILLED, OrderState.PARTIALLY_FILLED)
        )
        completed_slices = sum(
            1 for o in result.orders
            if o.state in (OrderState.FILLED, OrderState.PARTIALLY_FILLED)
        )
        avg_price = None
        if filled_qty > 0:
            prices = [
                o.average_fill_price or o.price or 0.0
                for o in result.orders
                if o.state in (OrderState.FILLED, OrderState.PARTIALLY_FILLED)
            ]
            if prices:
                avg_price = sum(prices) / len(prices)

        final_state = algorithm.build_algo_state(
            intent, slices,
            filled_qty=filled_qty,
            completed_slices=completed_slices,
            is_complete=True,
            avg_price=avg_price,
        )
        with self._lock:
            self._algo_states[intent.intent_id] = final_state

        # Emit completion event
        self._emit_event(ExecutionAlgorithmCompleted, intent, {
            "algorithm": algo_type.value,
            "status": result.status.value,
            "filled_quantity": filled_qty,
            "total_orders": len(result.orders),
        })

        # Write completion audit
        if self._execution_repository:
            record = ExecutionAuditRecord(
                execution_id=intent.execution_id,
                correlation_id=intent.correlation_id,
                actor="ems_engine",
                action="ALGORITHM_COMPLETE",
                before={"state": "EXECUTING"},
                after={
                    "status": result.status.value,
                    "filled_qty": filled_qty,
                    "orders": len(result.orders),
                },
                reason=f"EMS {algo_type.value} execution completed.",
            )
            self._execution_repository.save_audit_record(record)

        logger.info(
            "EMS: Intent %s execution completed. Status=%s, Filled=%.4f/%.4f.",
            intent.intent_id, result.status.value, filled_qty, intent.quantity,
        )
        return result

    def cancel_execution(self, intent_id: str) -> None:
        """Cancel an active algorithmic execution."""
        with self._lock:
            state = self._algo_states.get(intent_id)
            if state and not state.is_complete:
                updated = state.model_copy(update={
                    "is_cancelled": True,
                    "is_complete": True,
                    "updated_at": datetime.now(timezone.utc),
                })
                self._algo_states[intent_id] = updated
                logger.info("EMS: Cancelled execution for intent %s.", intent_id)

    def get_algo_state(self, intent_id: str) -> Optional[ExecutionAlgorithmState]:
        """Retrieve the algorithm state for an intent."""
        with self._lock:
            return self._algo_states.get(intent_id)

    def get_active_executions(self) -> List[ExecutionAlgorithmState]:
        """Retrieve all active (non-complete) algorithm states."""
        with self._lock:
            return [s for s in self._algo_states.values() if not s.is_complete]

    def get_all_executions(self) -> List[ExecutionAlgorithmState]:
        """Retrieve all algorithm execution states."""
        with self._lock:
            return list(self._algo_states.values())

    def _emit_event(self, event_class: type, intent: OrderIntent, extra: Dict[str, Any] = None) -> None:
        """Emit an event through the event bus if available."""
        if self._event_bus is None:
            return
        try:
            payload = {
                "intent_id": intent.intent_id,
                "execution_id": intent.execution_id,
                "symbol": intent.symbol,
            }
            if extra:
                payload.update(extra)
            event = event_class(source="ems_engine", payload=payload)
            self._event_bus.publish(event)
        except Exception as e:
            logger.warning("EMS: Failed to emit event %s: %s", event_class.__name__, e)
