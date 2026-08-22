"""VWAP (Volume-Weighted Average Price) Execution Algorithm.

Distributes the parent order across slices weighted by a volume
profile curve. Uses larger slices during high-volume periods
and smaller slices during low-volume periods.
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

# Default volume profile weights (U-shaped curve: higher at open/close)
_DEFAULT_VOLUME_PROFILE = [0.15, 0.12, 0.08, 0.07, 0.06, 0.06, 0.07, 0.08, 0.12, 0.19]


class VwapAlgorithm(BaseExecutionAlgorithm):
    """Volume-Weighted Average Price execution algorithm.

    Parameters (via intent.algo_params):
        - num_slices (int): Number of slices. Default: 10.
        - interval_seconds (float): Seconds between slices. Default: 60.
        - volume_profile (list[float]): Normalized weights. Default: U-shaped curve.
    """

    def __init__(self) -> None:
        super().__init__(ExecutionAlgorithmType.VWAP)

    def generate_slices(
        self,
        intent: OrderIntent,
        adapter: IBrokerAdapter,
    ) -> List[ExecutionSlice]:
        num_slices = intent.algo_params.get("num_slices", 10)
        interval_seconds = intent.algo_params.get("interval_seconds", 60.0)
        volume_profile = intent.algo_params.get("volume_profile", _DEFAULT_VOLUME_PROFILE)

        # Normalize profile to match slice count
        if len(volume_profile) != num_slices:
            # Resample: distribute evenly or truncate/extend
            if len(volume_profile) > num_slices:
                volume_profile = volume_profile[:num_slices]
            else:
                # Extend with equal weights
                extra = num_slices - len(volume_profile)
                avg_weight = 1.0 / num_slices
                volume_profile = volume_profile + [avg_weight] * extra

        # Normalize weights to sum to 1.0
        total_weight = sum(volume_profile)
        if total_weight > 0:
            volume_profile = [w / total_weight for w in volume_profile]

        now = datetime.now(timezone.utc)
        slices = []

        for i in range(num_slices):
            slice_qty = round(intent.quantity * volume_profile[i], 8)
            scheduled = now + timedelta(seconds=interval_seconds * i)

            slices.append(ExecutionSlice(
                slice_id=f"vwap-{uuid.uuid4().hex[:8]}",
                algo_id=f"vwap-{intent.intent_id}",
                intent_id=intent.intent_id,
                execution_id=intent.execution_id,
                slice_index=i,
                quantity=slice_qty,
                price=intent.price,
                scheduled_at=scheduled,
            ))

        logger.info(
            "VWAP: Generated %d weighted slices for %s (total=%.4f).",
            num_slices, intent.symbol, intent.quantity,
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
                logger.error("VWAP: Slice %d failed for %s: %s", s.slice_index, intent.symbol, e)
                failed_order = child_order.model_copy(update={
                    "state": OrderState.REJECTED,
                    "error_message": str(e),
                    "updated_at": datetime.now(timezone.utc),
                })
                orders.append(failed_order)

            # Minimal delay in paper mode
            time.sleep(min(intent.algo_params.get("interval_seconds", 60.0), 0.01))

        status = ExecutionStatus.EXECUTED if total_filled > 0 else ExecutionStatus.FAILED
        logger.info(
            "VWAP: Completed for %s. Filled=%.4f/%.4f.",
            intent.symbol, total_filled, intent.quantity,
        )
        return self.build_execution_result(intent, orders, fills, status)
