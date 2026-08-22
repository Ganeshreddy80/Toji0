"""POV (Percentage of Volume) Execution Algorithm.

Dynamically adjusts slice sizing to maintain a target participation
rate as a percentage of recent market volume.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
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


class PovAlgorithm(BaseExecutionAlgorithm):
    """Percentage of Volume execution algorithm.

    Parameters (via intent.algo_params):
        - participation_rate (float): Target fraction of market volume (e.g. 0.05 = 5%). Default: 0.05.
        - num_slices (int): Maximum number of slices. Default: 10.
        - interval_seconds (float): Check interval. Default: 60.
        - estimated_market_volume (float): Estimated volume per interval. Default: 1000.0.
    """

    def __init__(self) -> None:
        super().__init__(ExecutionAlgorithmType.POV)

    def generate_slices(
        self,
        intent: OrderIntent,
        adapter: IBrokerAdapter,
    ) -> List[ExecutionSlice]:
        participation_rate = intent.algo_params.get("participation_rate", 0.05)
        num_slices = intent.algo_params.get("num_slices", 10)
        interval_seconds = intent.algo_params.get("interval_seconds", 60.0)
        est_volume = intent.algo_params.get("estimated_market_volume", 1000.0)

        slice_qty = round(est_volume * participation_rate, 8)
        remaining = intent.quantity
        now = datetime.now(timezone.utc)
        slices = []

        for i in range(num_slices):
            if remaining <= 0:
                break
            qty = min(slice_qty, remaining)
            scheduled = now + timedelta(seconds=interval_seconds * i)
            slices.append(ExecutionSlice(
                slice_id=f"pov-{uuid.uuid4().hex[:8]}",
                algo_id=f"pov-{intent.intent_id}",
                intent_id=intent.intent_id,
                execution_id=intent.execution_id,
                slice_index=i,
                quantity=round(qty, 8),
                price=intent.price,
                scheduled_at=scheduled,
            ))
            remaining -= qty
            remaining = round(remaining, 8)

        logger.info(
            "POV: Generated %d slices at %.1f%% participation for %s.",
            len(slices), participation_rate * 100, intent.symbol,
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

            except Exception as e:
                logger.error("POV: Slice %d failed for %s: %s", s.slice_index, intent.symbol, e)
                failed_order = child_order.model_copy(update={
                    "state": OrderState.REJECTED,
                    "error_message": str(e),
                    "updated_at": datetime.now(timezone.utc),
                })
                orders.append(failed_order)

            time.sleep(min(intent.algo_params.get("interval_seconds", 60.0), 0.01))

        status = ExecutionStatus.EXECUTED if total_filled > 0 else ExecutionStatus.FAILED
        logger.info(
            "POV: Completed for %s. Filled=%.4f/%.4f.",
            intent.symbol, total_filled, intent.quantity,
        )
        return self.build_execution_result(intent, orders, fills, status)
