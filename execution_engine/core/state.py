from __future__ import annotations

import threading
from typing import Dict, List, Optional, Tuple

from execution_engine.core.enums import OrderState
from execution_engine.core.interfaces import IExecutionStateStore
from execution_engine.core.models import ExecutionState, Order


class OrderBook:
    """Thread-safe in-memory registry of all orders, categorized by state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._orders_by_id: Dict[str, Order] = {}

    def add_or_update_order(self, order: Order) -> None:
        """Register or update an order in the book in a thread-safe manner."""
        with self._lock:
            self._orders_by_id[order.client_order_id] = order

    def get_order(self, client_order_id: str) -> Optional[Order]:
        """Load a single order by client identifier."""
        with self._lock:
            return self._orders_by_id.get(client_order_id)

    def get_orders_by_states(self, states: List[OrderState]) -> List[Order]:
        """Retrieve orders currently matching any of the specified states."""
        with self._lock:
            return [o for o in self._orders_by_id.values() if o.state in states]

    def get_open_orders(self) -> List[Order]:
        """Fetch all currently open (submitted or acknowledged) sub-orders."""
        open_states = [OrderState.SUBMITTED, OrderState.ACKNOWLEDGED, OrderState.PARTIALLY_FILLED]
        return self.get_orders_by_states(open_states)

    def get_working_orders(self) -> List[Order]:
        """Fetch all orders currently being processed (validated, queued, submitted, acknowledged)."""
        working_states = [
            OrderState.VALIDATED,
            OrderState.QUEUED,
            OrderState.SUBMITTED,
            OrderState.ACKNOWLEDGED,
            OrderState.PARTIALLY_FILLED,
        ]
        return self.get_orders_by_states(working_states)

    def get_all_orders(self) -> List[Order]:
        """Retrieve a copy of all tracked orders."""
        with self._lock:
            return list(self._orders_by_id.values())

    def clear(self) -> None:
        """Wipe the order registry."""
        with self._lock:
            self._orders_by_id.clear()


class ExecutionStateStore(IExecutionStateStore):
    """Thread-safe implementation of execution state cache."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: Dict[str, ExecutionState] = {}
        self.order_book = OrderBook()

    def get_execution_state(self, execution_id: str) -> Optional[ExecutionState]:
        """Retrieve execution state by UUID in a thread-safe manner."""
        with self._lock:
            return self._states.get(execution_id)

    def update_execution_state(self, state: ExecutionState) -> None:
        """Insert or replace an execution state inside the cache."""
        with self._lock:
            self._states[state.request.execution_id] = state
        
        # Synchronize order book references
        for order in state.orders:
            self.order_book.add_or_update_order(order)

    def get_all_execution_states(self) -> List[ExecutionState]:
        """Retrieve all execution states tracked in memory."""
        with self._lock:
            return list(self._states.values())

    def clear(self) -> None:
        """Purge all stored execution states and clear the order book."""
        with self._lock:
            self._states.clear()
        self.order_book.clear()
