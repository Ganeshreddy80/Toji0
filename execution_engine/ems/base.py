"""Base execution algorithm interface for the EMS layer.

All execution algorithms (TWAP, VWAP, Iceberg, POV, Bracket, OCO)
implement this abstract base class to provide a uniform execution interface.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from execution_engine.brokers.broker_interface import IBrokerAdapter
from execution_engine.core.enums import (
    ExecutionAlgorithmType,
    ExecutionStatus,
    OrderSide,
    OrderState,
    OrderType,
    OrderTimeInForce,
)
from execution_engine.core.models import (
    ExecutionAlgorithmState,
    ExecutionMetrics,
    ExecutionResult,
    ExecutionSlice,
    Order,
    OrderFill,
    OrderIntent,
)


class BaseExecutionAlgorithm(ABC):
    """Abstract base class for EMS execution algorithms.

    Subclasses must implement:
    - generate_slices(): Plan how to break the parent order into child slices.
    - execute(): Run the algorithmic execution loop.
    """

    def __init__(self, algorithm_type: ExecutionAlgorithmType) -> None:
        self._algorithm_type = algorithm_type

    @property
    def algorithm_type(self) -> ExecutionAlgorithmType:
        return self._algorithm_type

    @abstractmethod
    def generate_slices(
        self,
        intent: OrderIntent,
        adapter: IBrokerAdapter,
    ) -> List[ExecutionSlice]:
        """Plan child order slices from the parent intent.

        Returns:
            List of ExecutionSlice objects representing the planned execution.
        """
        ...

    @abstractmethod
    def execute(
        self,
        intent: OrderIntent,
        slices: List[ExecutionSlice],
        adapter: IBrokerAdapter,
    ) -> ExecutionResult:
        """Execute the slices against the broker adapter.

        Returns:
            ExecutionResult summarising the outcome of all child orders.
        """
        ...

    def create_child_order(
        self,
        intent: OrderIntent,
        slice_obj: ExecutionSlice,
        order_type: Optional[OrderType] = None,
    ) -> Order:
        """Helper: create a child Order from an intent and a slice."""
        order_id = f"child-{uuid.uuid4().hex[:8]}"
        return Order(
            client_order_id=order_id,
            execution_id=intent.execution_id,
            request_id=intent.request_id,
            signal_id=intent.signal_id,
            strategy_id=intent.strategy_id,
            position_id=intent.position_id,
            correlation_id=intent.correlation_id,
            symbol=intent.symbol,
            side=intent.side,
            order_type=order_type or intent.order_type,
            quantity=slice_obj.quantity,
            price=slice_obj.price or intent.price,
            stop_price=intent.stop_price,
            time_in_force=intent.time_in_force,
            state=OrderState.CREATED,
            execution_flags=intent.execution_flags,
        )

    def build_algo_state(
        self,
        intent: OrderIntent,
        slices: List[ExecutionSlice],
        filled_qty: float = 0.0,
        completed_slices: int = 0,
        is_complete: bool = False,
        is_cancelled: bool = False,
        avg_price: Optional[float] = None,
    ) -> ExecutionAlgorithmState:
        """Helper: build an ExecutionAlgorithmState snapshot."""
        remaining = intent.quantity - filled_qty
        progress = (filled_qty / intent.quantity * 100.0) if intent.quantity > 0 else 0.0
        return ExecutionAlgorithmState(
            algo_id=f"algo-{uuid.uuid4().hex[:8]}",
            intent_id=intent.intent_id,
            execution_id=intent.execution_id,
            correlation_id=intent.correlation_id,
            algorithm=self._algorithm_type,
            total_quantity=intent.quantity,
            filled_quantity=filled_qty,
            remaining_quantity=max(0.0, remaining),
            total_slices=len(slices),
            completed_slices=completed_slices,
            average_fill_price=avg_price,
            progress_pct=round(progress, 2),
            is_complete=is_complete,
            is_cancelled=is_cancelled,
            params=intent.algo_params,
        )

    def build_execution_result(
        self,
        intent: OrderIntent,
        orders: List[Order],
        fills: List[OrderFill],
        status: ExecutionStatus = ExecutionStatus.EXECUTED,
    ) -> ExecutionResult:
        """Helper: build the final ExecutionResult from completed orders/fills."""
        return ExecutionResult(
            execution_id=intent.execution_id,
            request_id=intent.request_id,
            correlation_id=intent.correlation_id,
            status=status,
            orders=orders,
            timestamp=datetime.now(timezone.utc),
        )
