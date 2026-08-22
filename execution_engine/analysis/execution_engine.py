from __future__ import annotations

import heapq
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from execution_engine.brokers.broker_router import BrokerRouter
from execution_engine.core.enums import (
    ExecutionAlgorithmType,
    ExecutionStatus,
    IntentState,
    OMSMode,
    OrderSide,
    OrderState,
    OrderType,
)
from execution_engine.core.exceptions import BrokerError, ExecutionEngineError, ValidationError
from execution_engine.core.interfaces import (
    IExecutionEngine,
    IExecutionRepository,
    IExecutionStateStore,
)
from execution_engine.core.models import (
    ExecutionConfig,
    ExecutionJournalEntry,
    ExecutionMetrics,
    ExecutionRequest,
    ExecutionResult,
    ExecutionState,
    OMSConfig,
    Order,
    OrderFill,
    OrderIntent,
)
from execution_engine.core.state_machine import OrderStateMachine
from execution_engine.core.validator import ExecutionValidator
from execution_engine.analysis.metrics import ExecutionMetricsCalculator
from execution_engine.analysis.retry_manager import RetryManager
from execution_engine.analysis.risk_guard import ExecutionRiskGuard
from execution_engine.core.audit import ExecutionAuditRecord
from execution_engine.oms.oms_core import OmsCore
from execution_engine.ems.ems_engine import EmsEngine

logger = logging.getLogger(__name__)


class PriorityExecutionQueue:
    """Thread-safe priority execution queue prioritizing critical order types (e.g. stop/limit over market/rebalances)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Elements structure: (priority, enqueue_time, request)
        # Priority mapping: STOP_LIMIT/STOP_MARKET (0), LIMIT (1), MARKET (2)
        self._queue: List[Tuple[int, float, ExecutionRequest]] = []

    def enqueue(self, request: ExecutionRequest) -> None:
        """Add request to queue with priority sorting."""
        priority = 2  # default MARKET / rebalance
        if request.order_type in (OrderType.STOP_LIMIT, OrderType.STOP_MARKET):
            priority = 0
        elif request.order_type == OrderType.LIMIT:
            priority = 1

        with self._lock:
            heapq.heappush(self._queue, (priority, time.perf_counter(), request))
            logger.info("ExecutionQueue: Enqueued request %s with priority %d.", request.execution_id, priority)

    def dequeue(self) -> Optional[Tuple[float, ExecutionRequest]]:
        """Remove and return the highest priority request in queue."""
        with self._lock:
            if not self._queue:
                return None
            priority, enqueue_time, request = heapq.heappop(self._queue)
            wait_time_ms = (time.perf_counter() - enqueue_time) * 1000.0
            return wait_time_ms, request

    @property
    def depth(self) -> int:
        """Current queue depth."""
        with self._lock:
            return len(self._queue)


class ExecutionEngine(IExecutionEngine):
    """Core trade execution processor coordinating pre-trade checks, state machine transitions, and broker execution loops."""

    def __init__(
        self,
        config: ExecutionConfig,
        broker_router: BrokerRouter,
        validator: ExecutionValidator,
        repository: IExecutionRepository,
        state_store: IExecutionStateStore,
        analytics: Optional[Any] = None,
        oms: Optional[OmsCore] = None,
        ems: Optional[EmsEngine] = None,
    ) -> None:
        self._config = config
        self._broker_router = broker_router
        self._validator = validator
        self._repository = repository
        self._state_store = state_store
        
        from execution_engine.analysis.analytics import ExecutionAnalyticsCalculator
        self._analytics = analytics or ExecutionAnalyticsCalculator()
        
        self._queue = PriorityExecutionQueue()
        self._retry_manager = RetryManager(self._config.retry_policy)
        self._risk_guard = ExecutionRiskGuard(self._config)
        self._journal_seq = 0
        self._journal_lock = threading.Lock()

        # Initialize OMS / EMS
        oms_config = OMSConfig(
            mode=OMSMode.PAPER if self._config.broker_selection == "paper" else OMSMode.LIVE,
            default_broker_id=self._config.broker_selection,
        )
        self.oms = oms or OmsCore(
            config=oms_config,
            broker_router=self._broker_router,
            validator=self._validator,
            execution_repository=self._repository,
        )
        self.ems = ems or EmsEngine(
            broker_router=self._broker_router,
            execution_repository=self._repository,
        )

    def get_queue_depth(self) -> int:
        """Fetch current size of the execution priority queue."""
        return self._queue.depth

    def submit_execution(self, request: ExecutionRequest) -> ExecutionResult:
        """Submit a request to the queue, execute validation rules, and route order to the broker adapter."""
        # 1. Enqueue and Dequeue immediately (synchronous simulation with queue stats check)
        self._queue.enqueue(request)
        self._analytics.update_queue_stats(self._queue.depth)
        dequeue_info = self._queue.dequeue()
        self._analytics.update_queue_stats(self._queue.depth)
        if not dequeue_info:
            raise ExecutionEngineError("ExecutionEngine: Failed to dequeue execution request.")
        
        queue_wait_ms, dequeued_req = dequeue_info
        start_time = datetime.now(timezone.utc)

        # Update repository request record
        self._repository.save_request(dequeued_req)

        # Resolve broker adapter early for risk checks
        broker_id = self._config.broker_selection
        adapter = self._broker_router.get_adapter(broker_id)

        # 2. Pre-trade checks & validation latency tracing
        val_start = time.perf_counter()
        violations = self._validator.validate_request(dequeued_req, self._state_store)
        
        # Risk Guard Check
        risk_violations = self._risk_guard.check_request(dequeued_req, adapter)
        if risk_violations:
            violations.extend(risk_violations)

        validation_time_ms = (time.perf_counter() - val_start) * 1000.0

        # Construct OrderIntent
        intent = OrderIntent(
            intent_id=f"intent-{dequeued_req.execution_id}",
            execution_id=dequeued_req.execution_id,
            request_id=dequeued_req.request_id,
            signal_id=dequeued_req.signal_id,
            strategy_id=dequeued_req.strategy_id,
            position_id=dequeued_req.position_id,
            correlation_id=dequeued_req.correlation_id,
            symbol=dequeued_req.symbol,
            timeframe=dequeued_req.timeframe,
            side=dequeued_req.side,
            order_type=dequeued_req.order_type,
            algorithm=getattr(dequeued_req, "algorithm", ExecutionAlgorithmType.DIRECT),
            quantity=dequeued_req.quantity,
            price=dequeued_req.price,
            stop_price=dequeued_req.stop_price,
            time_in_force=dequeued_req.time_in_force,
            leverage=dequeued_req.leverage,
            margin_required=dequeued_req.margin_required,
            bracket_stop_loss=getattr(dequeued_req, "bracket_stop_loss", None),
            bracket_take_profit=getattr(dequeued_req, "bracket_take_profit", None),
            oco_stop_price=getattr(dequeued_req, "oco_stop_price", None),
            trailing_stop_callback_rate=getattr(dequeued_req, "trailing_stop_callback_rate", None),
            iceberg_display_quantity=getattr(dequeued_req, "iceberg_display_quantity", None),
            execution_flags=getattr(dequeued_req, "execution_flags", []),
            algo_params=getattr(dequeued_req, "algo_params", {}),
        )

        # 3. Submit intent to OMS
        routed_intent = self.oms.submit_intent(intent, external_violations=violations)

        if routed_intent.state == IntentState.REJECTED:
            logger.warning(
                "ExecutionEngine: Pre-trade validation failed for %s. Violations: %s",
                dequeued_req.execution_id,
                routed_intent.rejection_reasons,
            )
            # Create a rejected child order for backwards compatibility
            rejected_order = Order(
                client_order_id=f"rejected-{dequeued_req.execution_id}",
                execution_id=dequeued_req.execution_id,
                request_id=dequeued_req.request_id,
                signal_id=dequeued_req.signal_id,
                strategy_id=dequeued_req.strategy_id,
                position_id=dequeued_req.position_id,
                correlation_id=dequeued_req.correlation_id,
                symbol=dequeued_req.symbol,
                side=dequeued_req.side,
                order_type=dequeued_req.order_type,
                quantity=dequeued_req.quantity,
                price=dequeued_req.price,
                stop_price=dequeued_req.stop_price,
                time_in_force=dequeued_req.time_in_force,
                state=OrderState.REJECTED,
                error_message="; ".join(routed_intent.rejection_reasons),
            )
            self._repository.save_order(rejected_order)
            self._analytics.record_order(rejected_order)

            # Write immutable audit log
            audit_record = ExecutionAuditRecord(
                execution_id=dequeued_req.execution_id,
                correlation_id=dequeued_req.correlation_id,
                actor="risk_guard" if risk_violations else "validator",
                action="REJECT",
                before={"state": "QUEUED"},
                after={"state": "REJECTED", "violations": routed_intent.rejection_reasons},
                reason="Pre-trade validation or risk guard checks failed.",
            )
            self._repository.save_audit_record(audit_record)
            
            result = ExecutionResult(
                execution_id=dequeued_req.execution_id,
                request_id=dequeued_req.request_id,
                correlation_id=dequeued_req.correlation_id,
                status=ExecutionStatus.REJECTED,
                orders=[rejected_order],
                timestamp=datetime.now(timezone.utc),
            )
            self._repository.save_result(result)
            return result

        # 4. Route intent to EMS for execution
        broker_start = time.perf_counter()
        journal_entries: List[ExecutionJournalEntry] = []
        orders: List[Order] = []
        
        self._log_journal(dequeued_req.execution_id, dequeued_req.correlation_id, None, OrderState.VALIDATED, "Pre-trade validation successful.", journal_entries)
        self._log_journal(dequeued_req.execution_id, dequeued_req.correlation_id, OrderState.VALIDATED, OrderState.QUEUED, f"Order placed in priority queue. Wait time was {queue_wait_ms:.2f}ms.", journal_entries)
        self._log_journal(dequeued_req.execution_id, dequeued_req.correlation_id, OrderState.QUEUED, OrderState.SUBMITTED, f"Sending order to broker adapter: {broker_id}.", journal_entries)

        try:
            # Execute algorithmic execution
            ems_result = self.ems.execute_intent(routed_intent, broker_id)
            broker_latency_ms = (time.perf_counter() - broker_start) * 1000.0

            # Complete or Fail the intent in OMS
            if ems_result.status == ExecutionStatus.EXECUTED:
                self.oms.complete_intent(routed_intent.intent_id)
            else:
                self.oms.fail_intent(routed_intent.intent_id, "EMS execution failed or unfilled.")

            orders = ems_result.orders or []
            
            # Map child order states for journal logging and audit trace
            for order in orders:
                self._repository.save_order(order)
                self._analytics.record_order(order)
                self._log_journal(
                    dequeued_req.execution_id,
                    dequeued_req.correlation_id,
                    OrderState.SUBMITTED,
                    order.state,
                    f"OMS/EMS processed order: {order.state.value}.",
                    journal_entries,
                    broker_response=f"ID={order.broker_order_id}",
                )

        except Exception as ex:
            broker_latency_ms = (time.perf_counter() - broker_start) * 1000.0
            self.oms.fail_intent(routed_intent.intent_id, str(ex))

            fallback_order = Order(
                client_order_id=f"failed-{dequeued_req.execution_id}",
                execution_id=dequeued_req.execution_id,
                request_id=dequeued_req.request_id,
                signal_id=dequeued_req.signal_id,
                strategy_id=dequeued_req.strategy_id,
                position_id=dequeued_req.position_id,
                correlation_id=dequeued_req.correlation_id,
                symbol=dequeued_req.symbol,
                side=dequeued_req.side,
                order_type=dequeued_req.order_type,
                quantity=dequeued_req.quantity,
                price=dequeued_req.price,
                stop_price=dequeued_req.stop_price,
                time_in_force=dequeued_req.time_in_force,
                state=OrderState.REJECTED,
                error_message=str(ex),
            )
            orders = [fallback_order]

            self._log_journal(
                dequeued_req.execution_id,
                dequeued_req.correlation_id,
                OrderState.SUBMITTED,
                OrderState.REJECTED,
                f"Broker submission threw error: {ex}.",
                journal_entries,
                broker_response=str(ex),
            )
            self._repository.save_order(fallback_order)
            self._analytics.record_order(fallback_order)

        # 5. Extract fills from broker log and save them
        adapter_fills = getattr(adapter, "_fills_log", [])
        matched_fills = []
        for order in orders:
            order_fills = [f for f in adapter_fills if f.client_order_id == order.client_order_id]
            for fill in order_fills:
                self._repository.save_fill(fill)
                matched_fills.append(fill)

        # 6. Assemble metrics
        end_time = datetime.now(timezone.utc)
        metrics = ExecutionMetricsCalculator.compute_metrics(
            execution_id=dequeued_req.execution_id,
            correlation_id=dequeued_req.correlation_id,
            start_time=start_time,
            end_time=end_time,
            queue_wait_ms=queue_wait_ms,
            validation_time_ms=validation_time_ms,
            network_latency_ms=10.0,
            broker_latency_ms=broker_latency_ms,
            orders=orders,
            fills=matched_fills,
            retry_count=0,
        )

        status_outcome = ExecutionStatus.EXECUTED if any(o.state == OrderState.FILLED for o in orders) else ExecutionStatus.FAILED
        if any(o.state == OrderState.PARTIALLY_FILLED for o in orders):
            status_outcome = ExecutionStatus.EXECUTED

        result = ExecutionResult(
            execution_id=dequeued_req.execution_id,
            request_id=dequeued_req.request_id,
            correlation_id=dequeued_req.correlation_id,
            status=status_outcome,
            orders=orders,
            metrics=metrics,
            timestamp=end_time,
        )

        self._repository.save_result(result)
        if metrics:
            self._analytics.record_metrics(metrics)

        exec_state = ExecutionState(
            symbol=dequeued_req.symbol,
            timeframe=dequeued_req.timeframe,
            request=dequeued_req,
            orders=orders,
            result=result,
            journal=journal_entries,
            updated_at=end_time,
        )
        self._state_store.update_execution_state(exec_state)

        logger.info(
            "ExecutionEngine: Execution workflow completed with status %s for symbol %s.",
            status_outcome.value,
            dequeued_req.symbol,
        )
        return result

    def _log_journal(
        self,
        execution_id: str,
        correlation_id: str,
        prev_state: Optional[OrderState],
        new_state: OrderState,
        reason: str,
        journal_list: List[ExecutionJournalEntry],
        broker_response: Optional[str] = None,
    ) -> None:
        """Create and persist an immutable ExecutionJournalEntry."""
        with self._journal_lock:
            self._journal_seq += 1
            seq = self._journal_seq

        entry = ExecutionJournalEntry(
            journal_sequence_number=seq,
            execution_id=execution_id,
            correlation_id=correlation_id,
            timestamp=datetime.now(timezone.utc),
            previous_state=prev_state,
            new_state=new_state,
            reason=reason,
            broker_response=broker_response,
        )
        journal_list.append(entry)
        self._repository.save_journal_entry(entry)
        
        # Structured log print
        logger.info(
            "Structured Log | FSM Transition: seq=%d | execution_id=%s | previous=%s | new=%s | reason=%s",
            seq,
            execution_id,
            prev_state.value if prev_state else "None",
            new_state.value,
            reason,
        )
