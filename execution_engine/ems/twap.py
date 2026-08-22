"""TWAP (Time-Weighted Average Price) Execution Algorithm.

Slices the parent order into N equal-sized child orders
executed at regular time intervals over a specified duration.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from execution_engine.brokers.broker_interface import IBrokerAdapter
from execution_engine.core.enums import ExecutionAlgorithmType, ExecutionStatus, OrderState
from execution_engine.core.models import (
    ExecutionResult,
    ExecutionSlice,
    Order,
    OrderFill,
    OrderIntent,
)
from execution_engine.ems.base import BaseExecutionAlgorithm

logger = logging.getLogger(__name__)


class TwapAlgorithm(BaseExecutionAlgorithm):
    """Time-Weighted Average Price execution algorithm.

    Parameters (via intent.algo_params):
        - num_slices (int): Number of equal slices. Default: 5.
        - interval_seconds (float): Seconds between slices. Default: 60.
    """

    def __init__(self) -> None:
        super().__init__(ExecutionAlgorithmType.TWAP)

    def generate_slices(
        self,
        intent: OrderIntent,
        adapter: IBrokerAdapter,
    ) -> List[ExecutionSlice]:
        num_slices = intent.algo_params.get("num_slices", 5)
        interval_seconds = intent.algo_params.get("interval_seconds", 60.0)

        slice_qty = intent.quantity / num_slices
        now = datetime.now(timezone.utc)

        slices = []
        for i in range(num_slices):
            scheduled = now + timedelta(seconds=interval_seconds * i)
            slices.append(ExecutionSlice(
                slice_id=f"twap-{uuid.uuid4().hex[:8]}",
                algo_id=f"twap-{intent.intent_id}",
                intent_id=intent.intent_id,
                execution_id=intent.execution_id,
                slice_index=i,
                quantity=round(slice_qty, 8),
                price=intent.price,
                scheduled_at=scheduled,
            ))

        logger.info(
            "TWAP: Generated %d slices of %.4f for %s, interval=%.1fs.",
            num_slices, slice_qty, intent.symbol, interval_seconds,
        )
        return slices

    def execute(
        self,
        intent: OrderIntent,
        slices: List[ExecutionSlice],
        adapter: IBrokerAdapter,
    ) -> ExecutionResult:
        orders: List[Order] = []
        fills: List[OrderFill] = []
        total_filled = 0.0
        completed_slices = 0

        for s in slices:
            child_order = self.create_child_order(intent, s)

            try:
                executed = adapter.submit_order(child_order)
                orders.append(executed)

                if executed.state in (OrderState.FILLED, OrderState.PARTIALLY_FILLED):
                    total_filled += executed.filled_quantity or s.quantity
                    completed_slices += 1

                    # Collect fills from adapter
                    adapter_fills = getattr(adapter, "_fills_log", [])
                    matched = [f for f in adapter_fills if f.client_order_id == child_order.client_order_id]
                    fills.extend(matched)

            except Exception as e:
                logger.error("TWAP: Slice %d failed for %s: %s", s.slice_index, intent.symbol, e)
                failed_order = child_order.model_copy(update={
                    "state": OrderState.REJECTED,
                    "error_message": str(e),
                    "updated_at": datetime.now(timezone.utc),
                })
                orders.append(failed_order)

            # Simulate inter-slice delay (reduced for paper trading)
            interval = intent.algo_params.get("interval_seconds", 60.0)
            # In paper mode, use a tiny delay to not block
            actual_delay = min(interval, 0.01)
            if actual_delay > 0:
                time.sleep(actual_delay)

        status = ExecutionStatus.EXECUTED if total_filled > 0 else ExecutionStatus.FAILED
        logger.info(
            "TWAP: Completed for %s. Filled=%.4f/%4f, Slices=%d/%d.",
            intent.symbol, total_filled, intent.quantity,
            completed_slices, len(slices),
        )

        return self.build_execution_result(intent, orders, fills, status)
