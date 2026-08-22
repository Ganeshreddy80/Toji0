"""Institutional Order Management System Core.

The OMS Core is the central coordinator for the order lifecycle:
1. Receives OrderIntents from the upstream pipeline.
2. Validates against exchange rules, capital limits, and open position constraints.
3. Routes approved intents to the EMS for algorithmic execution.
4. Tracks the full lifecycle via the IntentStateMachine.
5. Publishes events at every state transition for downstream consumers.
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
    IntentState,
    OMSMode,
    OrderSide,
    OrderState,
    OrderType,
    RoutingStrategy,
)
from execution_engine.core.events import (
    OrderIntentApproved,
    OrderIntentCreated,
    OrderIntentRejected,
    OrderIntentValidated,
    OrderRouted,
    BrokerSelected,
    OMSStateChanged,
)
from execution_engine.core.exceptions import ExecutionEngineError
from execution_engine.core.models import (
    BrokerStatus,
    ExecutionRequest,
    ExecutionResult,
    OMSConfig,
    OMSState,
    Order,
    OrderIntent,
    RoutingDecision,
)
from execution_engine.core.state_machine import IntentStateMachine
from execution_engine.core.validator import ExecutionValidator

logger = logging.getLogger(__name__)


class IntentStore:
    """Thread-safe in-memory store for OrderIntent lifecycle tracking."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._intents: Dict[str, OrderIntent] = {}

    def add_intent(self, intent: OrderIntent) -> None:
        with self._lock:
            self._intents[intent.intent_id] = intent

    def update_intent(self, intent: OrderIntent) -> None:
        with self._lock:
            self._intents[intent.intent_id] = intent

    def get_intent(self, intent_id: str) -> Optional[OrderIntent]:
        with self._lock:
            return self._intents.get(intent_id)

    def get_active_intents(self) -> List[OrderIntent]:
        with self._lock:
            return [
                i for i in self._intents.values()
                if IntentStateMachine.is_active(i.state)
            ]

    def get_all_intents(self) -> List[OrderIntent]:
        with self._lock:
            return list(self._intents.values())

    def clear(self) -> None:
        with self._lock:
            self._intents.clear()


class OmsRepository:
    """In-memory persistence layer for OMS-specific data."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._intents: List[OrderIntent] = []
        self._routing_decisions: List[RoutingDecision] = []
        self._oms_states: List[OMSState] = []

    def save_intent(self, intent: OrderIntent) -> None:
        with self._lock:
            self._intents.append(intent)

    def save_routing_decision(self, decision: RoutingDecision) -> None:
        with self._lock:
            self._routing_decisions.append(decision)

    def save_oms_state(self, state: OMSState) -> None:
        with self._lock:
            self._oms_states.append(state)

    def load_active_intents(self) -> List[OrderIntent]:
        with self._lock:
            return [
                i for i in self._intents
                if IntentStateMachine.is_active(i.state)
            ]

    def load_routing_decisions(self, intent_id: Optional[str] = None) -> List[RoutingDecision]:
        with self._lock:
            if intent_id:
                return [d for d in self._routing_decisions if d.intent_id == intent_id]
            return list(self._routing_decisions)

    def get_latest_oms_state(self) -> Optional[OMSState]:
        with self._lock:
            return self._oms_states[-1] if self._oms_states else None


class OmsCore:
    """Institutional Order Management System Core.

    Coordinates the full order lifecycle from intent creation
    through validation, approval, routing, and execution.
    """

    def __init__(
        self,
        config: OMSConfig,
        broker_router: BrokerRouter,
        validator: ExecutionValidator,
        event_bus: Any = None,
        execution_repository: Any = None,
    ) -> None:
        self._config = config
        self._broker_router = broker_router
        self._validator = validator
        self._event_bus = event_bus
        self._execution_repository = execution_repository

        self._intent_store = IntentStore()
        self._oms_repository = OmsRepository()

        # Counters (guarded by lock)
        self._lock = threading.Lock()
        self._total_intents = 0
        self._completed_intents = 0
        self._rejected_intents = 0
        self._failed_intents = 0
        self._cancelled_intents = 0

    # ── Public API ────────────────────────────────────────────────────

    def submit_intent(self, intent: OrderIntent, external_violations: Optional[List[str]] = None) -> OrderIntent:
        """Process an OrderIntent through the full OMS lifecycle.

        Flow: CREATED → VALIDATING → VALIDATED → APPROVED → ROUTING → ROUTED
        Returns the intent in its final pre-execution state (ROUTED or REJECTED).
        """
        with self._lock:
            self._total_intents += 1

        logger.info("OMS: Received intent %s for %s %s %s",
                     intent.intent_id, intent.side.value, intent.quantity, intent.symbol)

        # Persist the initial intent
        self._oms_repository.save_intent(intent)
        self._intent_store.add_intent(intent)
        self._emit_event(OrderIntentCreated, intent)

        # Step 1: CREATED → VALIDATING
        intent = self._transition_intent(intent, IntentState.VALIDATING, "Starting OMS validation.")

        # Step 2: Validate
        violations = self._validate_intent(intent)
        if external_violations:
            violations.extend(external_violations)

        if violations:
            intent = self._transition_intent(
                intent, IntentState.REJECTED,
                f"Validation failed: {'; '.join(violations)}",
            )
            intent = intent.model_copy(update={"rejection_reasons": violations})
            self._intent_store.update_intent(intent)
            self._oms_repository.save_intent(intent)
            self._emit_event(OrderIntentRejected, intent)
            with self._lock:
                self._rejected_intents += 1
            self._publish_oms_state()
            return intent

        # Step 3: VALIDATING → VALIDATED
        intent = self._transition_intent(intent, IntentState.VALIDATED, "OMS validation passed.")
        self._emit_event(OrderIntentValidated, intent)

        # Step 4: VALIDATED → APPROVED
        intent = self._transition_intent(intent, IntentState.APPROVED, "Intent approved for routing.")
        self._emit_event(OrderIntentApproved, intent)

        # Step 5: APPROVED → ROUTING
        intent = self._transition_intent(intent, IntentState.ROUTING, "Selecting broker venue.")

        # Step 6: Route to broker
        broker_id = self._resolve_broker(intent)
        routing_decision = RoutingDecision(
            decision_id=f"rd-{uuid.uuid4().hex[:8]}",
            intent_id=intent.intent_id,
            execution_id=intent.execution_id,
            correlation_id=intent.correlation_id,
            broker_id=broker_id,
            strategy=self._config.default_routing,
            reason=f"Routed to {broker_id} via {self._config.default_routing.value} strategy.",
        )
        self._oms_repository.save_routing_decision(routing_decision)
        self._emit_event(BrokerSelected, intent)

        # Step 7: ROUTING → ROUTED
        intent = self._transition_intent(
            intent, IntentState.ROUTED,
            f"Routed to broker '{broker_id}'.",
        )
        self._emit_event(OrderRouted, intent)

        self._intent_store.update_intent(intent)
        self._oms_repository.save_intent(intent)
        self._publish_oms_state()

        logger.info("OMS: Intent %s routed to broker %s, ready for EMS execution.",
                     intent.intent_id, broker_id)
        return intent

    def complete_intent(self, intent_id: str) -> OrderIntent:
        """Mark an intent as COMPLETED after successful EMS execution."""
        intent = self._intent_store.get_intent(intent_id)
        if not intent:
            raise ExecutionEngineError(f"OMS: Intent {intent_id} not found.")

        intent = self._transition_intent(intent, IntentState.EXECUTING, "EMS execution started.")
        intent = self._transition_intent(intent, IntentState.COMPLETED, "Execution completed successfully.")
        self._intent_store.update_intent(intent)
        self._oms_repository.save_intent(intent)

        with self._lock:
            self._completed_intents += 1
        self._publish_oms_state()
        return intent

    def fail_intent(self, intent_id: str, reason: str) -> OrderIntent:
        """Mark an intent as FAILED after EMS execution failure."""
        intent = self._intent_store.get_intent(intent_id)
        if not intent:
            raise ExecutionEngineError(f"OMS: Intent {intent_id} not found.")

        intent = self._transition_intent(intent, IntentState.FAILED, f"Execution failed: {reason}")
        self._intent_store.update_intent(intent)
        self._oms_repository.save_intent(intent)

        with self._lock:
            self._failed_intents += 1
        self._publish_oms_state()
        return intent

    def cancel_intent(self, intent_id: str) -> OrderIntent:
        """Cancel an active intent."""
        intent = self._intent_store.get_intent(intent_id)
        if not intent:
            raise ExecutionEngineError(f"OMS: Intent {intent_id} not found.")

        if not IntentStateMachine.is_active(intent.state):
            raise ExecutionEngineError(
                f"OMS: Intent {intent_id} is in terminal state {intent.state.value}, cannot cancel."
            )

        intent = self._transition_intent(intent, IntentState.CANCELLED, "Cancelled by user/system.")
        self._intent_store.update_intent(intent)
        self._oms_repository.save_intent(intent)

        with self._lock:
            self._cancelled_intents += 1
        self._publish_oms_state()
        return intent

    def get_intent(self, intent_id: str) -> Optional[OrderIntent]:
        """Retrieve an intent by ID."""
        return self._intent_store.get_intent(intent_id)

    def get_active_intents(self) -> List[OrderIntent]:
        """Retrieve all active intents."""
        return self._intent_store.get_active_intents()

    def get_all_intents(self) -> List[OrderIntent]:
        """Retrieve all intents (active and terminal)."""
        return self._intent_store.get_all_intents()

    def get_oms_state(self) -> OMSState:
        """Compute the current OMS operational state snapshot."""
        with self._lock:
            active = self._intent_store.get_active_intents()
            return OMSState(
                total_intents=self._total_intents,
                active_intents=len(active),
                completed_intents=self._completed_intents,
                rejected_intents=self._rejected_intents,
                failed_intents=self._failed_intents,
                cancelled_intents=self._cancelled_intents,
            )

    def get_broker_statuses(self) -> List[BrokerStatus]:
        """Retrieve connection status for all registered brokers."""
        statuses = []
        try:
            adapters = self._broker_router._adapters
            for broker_id, adapter in adapters.items():
                is_connected = False
                latency = 0.0
                try:
                    is_connected = adapter.ping()
                except Exception:
                    pass
                statuses.append(BrokerStatus(
                    broker_id=broker_id,
                    is_connected=is_connected,
                    latency_ms=latency,
                ))
        except Exception as e:
            logger.error("OMS: Error fetching broker statuses: %s", e)
        return statuses

    def get_routing_decisions(self, intent_id: Optional[str] = None) -> List[RoutingDecision]:
        """Retrieve routing decision records."""
        return self._oms_repository.load_routing_decisions(intent_id)

    # ── Private Helpers ───────────────────────────────────────────────

    def _validate_intent(self, intent: OrderIntent) -> List[str]:
        """Run pre-trade validation checks against the intent."""
        violations: List[str] = []

        # Check open order limits
        active_count = len(self._intent_store.get_active_intents())
        if active_count >= self._config.max_open_intents:
            violations.append(
                f"Max open intents limit reached ({self._config.max_open_intents})."
            )

        # Check quantity
        if intent.quantity <= 0:
            violations.append("Quantity must be positive.")

        # Check price for limit orders
        if intent.order_type == OrderType.LIMIT and intent.price is None:
            violations.append("Limit orders require a price.")

        # Check stop price for stop orders
        if intent.order_type in (OrderType.STOP_LIMIT, OrderType.STOP_MARKET):
            if intent.stop_price is None:
                violations.append("Stop orders require a stop_price.")

        # Check bracket parameters
        if intent.algorithm == ExecutionAlgorithmType.BRACKET:
            if intent.bracket_stop_loss is None or intent.bracket_take_profit is None:
                violations.append("Bracket orders require both stop_loss and take_profit prices.")

        # Check iceberg display quantity
        if intent.algorithm == ExecutionAlgorithmType.ICEBERG:
            if intent.iceberg_display_quantity is None:
                violations.append("Iceberg orders require iceberg_display_quantity.")
            elif intent.iceberg_display_quantity >= intent.quantity:
                violations.append("Iceberg display quantity must be less than total quantity.")

        return violations

    def _resolve_broker(self, intent: OrderIntent) -> str:
        """Determine which broker adapter to use for this intent."""
        return self._config.default_broker_id

    def _transition_intent(
        self, intent: OrderIntent, new_state: IntentState, reason: str
    ) -> OrderIntent:
        """Validate and apply a state transition on an intent."""
        IntentStateMachine.validate_transition(intent.state, new_state)

        logger.info(
            "OMS FSM | intent=%s | %s → %s | reason=%s",
            intent.intent_id, intent.state.value, new_state.value, reason,
        )

        updated = intent.model_copy(update={
            "state": new_state,
            "updated_at": datetime.now(timezone.utc),
        })
        self._intent_store.update_intent(updated)

        # Write audit record
        if self._execution_repository:
            record = ExecutionAuditRecord(
                execution_id=intent.execution_id,
                correlation_id=intent.correlation_id,
                actor="oms_core",
                action="INTENT_TRANSITION",
                before={"state": intent.state.value},
                after={"state": new_state.value},
                reason=reason,
            )
            self._execution_repository.save_audit_record(record)

        return updated

    def _emit_event(self, event_class: type, intent: OrderIntent) -> None:
        """Emit an event through the event bus if available."""
        if self._event_bus is None:
            return
        try:
            event = event_class(
                source="oms_core",
                payload={
                    "intent_id": intent.intent_id,
                    "execution_id": intent.execution_id,
                    "symbol": intent.symbol,
                    "side": intent.side.value,
                    "quantity": intent.quantity,
                    "state": intent.state.value,
                    "algorithm": intent.algorithm.value,
                },
            )
            self._event_bus.publish(event)
        except Exception as e:
            logger.warning("OMS: Failed to emit event %s: %s", event_class.__name__, e)

    def _publish_oms_state(self) -> None:
        """Persist and emit the current OMS state snapshot."""
        state = self.get_oms_state()
        self._oms_repository.save_oms_state(state)
        if self._event_bus:
            try:
                event = OMSStateChanged(
                    source="oms_core",
                    payload={
                        "total_intents": state.total_intents,
                        "active_intents": state.active_intents,
                        "completed_intents": state.completed_intents,
                        "rejected_intents": state.rejected_intents,
                    },
                )
                self._event_bus.publish(event)
            except Exception as e:
                logger.warning("OMS: Failed to emit OMSStateChanged: %s", e)
