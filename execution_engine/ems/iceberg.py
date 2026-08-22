"""Iceberg Execution Algorithm.

Keeps only a small display quantity visible in the order book.
When a slice is filled, the next hidden slice is automatically submitted.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List

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


class IcebergAlgorithm(BaseExecutionAlgorithm):
    """Iceberg execution algorithm.

    Parameters (via intent):
        - iceberg_display_quantity: Visible slice size per round.
    """

    def __init__(self) -> None:
        super().__init__(ExecutionAlgorithmType.ICEBERG)

    def generate_slices(
        self,
        intent: OrderIntent,
        adapter: IBrokerAdapter,
    ) -> List[ExecutionSlice]:
        display_qty = intent.iceberg_display_quantity or (intent.quantity / 5.0)
        remaining = intent.quantity
        slices = []
        index = 0

        while remaining > 0:
            slice_qty = min(display_qty, remaining)
            slices.append(ExecutionSlice(
                slice_id=f"ice-{uuid.uuid4().hex[:8]}",
                algo_id=f"iceberg-{intent.intent_id}",
                intent_id=intent.intent_id,
                execution_id=intent.execution_id,
                slice_index=index,
                quantity=round(slice_qty, 8),
                price=intent.price,
            ))
            remaining -= slice_qty
            remaining = round(remaining, 8)
            index += 1

        logger.info(
            "Iceberg: Generated %d hidden slices of %.4f for %s.",
            len(slices), display_qty, intent.symbol,
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

        for s in slices:
            child_order = self.create_child_order(intent, s)

            try:
                executed = adapter.submit_order(child_order)
                orders.append(executed)

                if executed.state in (OrderState.FILLED, OrderState.PARTIALLY_FILLED):
                    total_filled += executed.filled_quantity or s.quantity

                    adapter_fills = getattr(adapter, "_fills_log", [])
                    matched = [f for f in adapter_fills if f.client_order_id == child_order.client_order_id]
                    fills.extend(matched)

                    logger.debug(
                        "Iceberg: Slice %d filled for %s, submitting next hidden slice.",
                        s.slice_index, intent.symbol,
                    )
                else:
                    # If a slice is rejected, stop the iceberg
                    logger.warning(
                        "Iceberg: Slice %d not filled (state=%s), stopping iceberg for %s.",
                        s.slice_index, executed.state.value, intent.symbol,
                    )
                    break

            except Exception as e:
                logger.error("Iceberg: Slice %d failed for %s: %s", s.slice_index, intent.symbol, e)
                failed_order = child_order.model_copy(update={
                    "state": OrderState.REJECTED,
                    "error_message": str(e),
                    "updated_at": datetime.now(timezone.utc),
                })
                orders.append(failed_order)
                break

        status = ExecutionStatus.EXECUTED if total_filled > 0 else ExecutionStatus.FAILED
        logger.info(
            "Iceberg: Completed for %s. Filled=%.4f/%.4f, Slices=%d/%d.",
            intent.symbol, total_filled, intent.quantity,
            sum(1 for o in orders if o.state == OrderState.FILLED), len(slices),
        )
        return self.build_execution_result(intent, orders, fills, status)
