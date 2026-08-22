from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from execution_engine.core.models import (
    BrokerStatus,
    ExecutionAlgorithmState,
    ExecutionHealthSnapshot,
    ExecutionRequest,
    ExecutionResult,
    ExecutionState,
    OMSConfig,
    OMSState,
    Order,
    OrderFill,
    OrderIntent,
    RoutingDecision,
)


class IExecutionStateStore(Protocol):
    """Protocol for the thread-safe in-memory execution state storage."""

    def get_execution_state(self, execution_id: str) -> Optional[ExecutionState]:
        ...

    def update_execution_state(self, state: ExecutionState) -> None:
        ...

    def get_all_execution_states(self) -> List[ExecutionState]:
        ...

    def clear(self) -> None:
        ...


class IExecutionRepository(Protocol):
    """Protocol for persisting execution requests, orders, fills, and metrics."""

    def save_request(self, request: ExecutionRequest) -> None:
        ...

    def save_order(self, order: Order) -> None:
        ...

    def save_fill(self, fill: OrderFill) -> None:
        ...

    def save_result(self, result: ExecutionResult) -> None:
        ...

    def save_journal_entry(self, entry: Any) -> None:
        ...

    def save_health_snapshot(self, snapshot: ExecutionHealthSnapshot) -> None:
        ...

    def save_audit_record(self, record: Any) -> None:
        ...

    def get_audit_records(self, execution_id: Optional[str] = None) -> List[Any]:
        ...

    def load_order(self, client_order_id: str) -> Optional[Order]:
        ...

    def load_latest_orders(self, limit: int = 100) -> List[Order]:
        ...


class IOrderValidator(Protocol):
    """Protocol for verifying that orders satisfy exchange and capital constraints."""

    def validate_request(self, request: ExecutionRequest, state_store: IExecutionStateStore) -> list[str]:
        ...


class IExecutionEngine(Protocol):
    """Protocol coordinating order execution flows and routing commands to brokers."""

    def submit_execution(self, request: ExecutionRequest) -> ExecutionResult:
        ...


# ── Sprint 8: Institutional OMS & EMS Protocols ──────────────────────────


class IIntentStore(Protocol):
    """Thread-safe in-memory store for OrderIntent lifecycle tracking."""

    def add_intent(self, intent: OrderIntent) -> None:
        ...

    def update_intent(self, intent: OrderIntent) -> None:
        ...

    def get_intent(self, intent_id: str) -> Optional[OrderIntent]:
        ...

    def get_active_intents(self) -> List[OrderIntent]:
        ...

    def get_all_intents(self) -> List[OrderIntent]:
        ...

    def clear(self) -> None:
        ...


class IOmsRepository(Protocol):
    """Persistence layer for OMS-specific data (intents, routing, algo states)."""

    def save_intent(self, intent: OrderIntent) -> None:
        ...

    def save_routing_decision(self, decision: RoutingDecision) -> None:
        ...

    def save_algo_state(self, state: ExecutionAlgorithmState) -> None:
        ...

    def save_oms_state(self, state: OMSState) -> None:
        ...

    def load_active_intents(self) -> List[OrderIntent]:
        ...

    def load_routing_decisions(self, intent_id: Optional[str] = None) -> List[RoutingDecision]:
        ...

    def load_algo_states(self, intent_id: Optional[str] = None) -> List[ExecutionAlgorithmState]:
        ...


class IOmsCore(Protocol):
    """Protocol for the institutional Order Management System core."""

    def submit_intent(self, intent: OrderIntent) -> OrderIntent:
        ...

    def cancel_intent(self, intent_id: str) -> OrderIntent:
        ...

    def get_intent(self, intent_id: str) -> Optional[OrderIntent]:
        ...

    def get_active_intents(self) -> List[OrderIntent]:
        ...

    def get_oms_state(self) -> OMSState:
        ...

    def get_broker_statuses(self) -> List[BrokerStatus]:
        ...


class IEmsEngine(Protocol):
    """Protocol for the Execution Management System algorithmic engine."""

    def execute_intent(self, intent: OrderIntent, broker_id: str) -> ExecutionResult:
        ...

    def cancel_execution(self, intent_id: str) -> None:
        ...

    def get_algo_state(self, intent_id: str) -> Optional[ExecutionAlgorithmState]:
        ...

    def get_active_executions(self) -> List[ExecutionAlgorithmState]:
        ...

