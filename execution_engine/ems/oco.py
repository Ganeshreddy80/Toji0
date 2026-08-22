"""OCO (One-Cancels-the-Other) Execution Algorithm.

Links two child orders (e.g. limit buy + stop sell).
When one fills, the other is automatically cancelled.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from execution_engine.brokers.broker_interface import IBrokerAdapter
from execution_engine.core.enums import (
    ExecutionAlgorithmType,
    ExecutionStatus,
    OrderSide,
    OrderState,
    OrderType,
)
from execution_engine.core.models import (
    ExecutionResult,
    ExecutionSlice,
    Order,
    OrderFill,
    OrderIntent,
)
from execution_engine.ems.base import BaseExecutionAlgorithm

logger = logging.getLogger(__name__)


class OcoAlgorithm(BaseExecutionAlgorithm):
    """One-Cancels-the-Other execution algorithm.

    Submits two linked orders:
    1. Primary limit/market order.
    2. Secondary stop order (from oco_stop_price).

    When one fills, the other is cancelled.

    Parameters (via intent):
        - oco_stop_price: Stop trigger price for the secondary leg.
    """

    def __init__(self) -> None:
        super().__init__(ExecutionAlgorithmType.OCO)

    def generate_slices(
        self,
        intent: OrderIntent,
        adapter: IBrokerAdapter,
    ) -> List[ExecutionSlice]:
        slices = []

        # Slice 0: Primary order (limit or market)
        slices.append(ExecutionSlice(
            slice_id=f"oco-primary-{uuid.uuid4().hex[:8]}",
            algo_id=f"oco-{intent.intent_id}",
            intent_id=intent.intent_id,
            execution_id=intent.execution_id,
            slice_index=0,
            quantity=intent.quantity,
            price=intent.price,
        ))

        # Slice 1: Secondary stop order
        if intent.oco_stop_price is not None:
            slices.append(ExecutionSlice(
                slice_id=f"oco-stop-{uuid.uuid4().hex[:8]}",
                algo_id=f"oco-{intent.intent_id}",
                intent_id=intent.intent_id,
                execution_id=intent.execution_id,
                slice_index=1,
                quantity=intent.quantity,
                price=intent.oco_stop_price,
            ))

        logger.info(
            "OCO: Generated %d linked legs for %s.",
            len(slices), intent.symbol,
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

        if len(slices) < 2:
            # Fall back to direct execution if no OCO pair
            if slices:
                child = self.create_child_order(intent, slices[0])
                try:
                    executed = adapter.submit_order(child)
                    orders.append(executed)
                except Exception as e:
                    logger.error("OCO: Primary order failed: %s", e)
            status = ExecutionStatus.EXECUTED if any(
                o.state == OrderState.FILLED for o in orders
            ) else ExecutionStatus.FAILED
            return self.build_execution_result(intent, orders, fills, status)

        # Submit primary order
        primary_slice = slices[0]
        primary_order = self.create_child_order(intent, primary_slice)

        # Submit secondary stop order
        secondary_slice = slices[1]
        secondary_order = Order(
            client_order_id=f"oco-stop-{uuid.uuid4().hex[:8]}",
            execution_id=intent.execution_id,
            request_id=intent.request_id,
            signal_id=intent.signal_id,
            strategy_id=intent.strategy_id,
            position_id=intent.position_id,
            correlation_id=intent.correlation_id,
            symbol=intent.symbol,
            side=intent.side,
            order_type=OrderType.STOP_MARKET,
            quantity=secondary_slice.quantity,
            stop_price=secondary_slice.price,
            time_in_force=intent.time_in_force,
            state=OrderState.CREATED,
        )

        # Submit both
        executed_primary = None
        executed_secondary = None

        try:
            executed_primary = adapter.submit_order(primary_order)
            orders.append(executed_primary)
        except Exception as e:
            logger.error("OCO: Primary order submission failed: %s", e)
            failed = primary_order.model_copy(update={
                "state": OrderState.REJECTED,
                "error_message": str(e),
                "updated_at": datetime.now(timezone.utc),
            })
            orders.append(failed)

        try:
            executed_secondary = adapter.submit_order(secondary_order)
            orders.append(executed_secondary)
        except Exception as e:
            logger.error("OCO: Secondary stop order submission failed: %s", e)
            failed = secondary_order.model_copy(update={
                "state": OrderState.REJECTED,
                "error_message": str(e),
                "updated_at": datetime.now(timezone.utc),
            })
            orders.append(failed)

        # Check for OCO cancellation logic
        if executed_primary and executed_primary.state in (OrderState.FILLED, OrderState.PARTIALLY_FILLED):
            # Primary filled — cancel secondary
            if executed_secondary and executed_secondary.state not in (
                OrderState.FILLED, OrderState.REJECTED, OrderState.CANCELLED,
            ):
                try:
                    cancelled = adapter.cancel_order(executed_secondary.client_order_id)
                    orders.append(cancelled)
                    logger.info("OCO: Cancelled secondary stop after primary fill.")
                except Exception as e:
                    logger.warning("OCO: Failed to cancel secondary: %s", e)

            adapter_fills = getattr(adapter, "_fills_log", [])
            matched = [f for f in adapter_fills if f.client_order_id == primary_order.client_order_id]
            fills.extend(matched)

        elif executed_secondary and executed_secondary.state in (OrderState.FILLED, OrderState.PARTIALLY_FILLED):
            # Secondary filled — cancel primary
            if executed_primary and executed_primary.state not in (
                OrderState.FILLED, OrderState.REJECTED, OrderState.CANCELLED,
            ):
                try:
                    cancelled = adapter.cancel_order(executed_primary.client_order_id)
                    orders.append(cancelled)
                    logger.info("OCO: Cancelled primary after secondary stop fill.")
                except Exception as e:
                    logger.warning("OCO: Failed to cancel primary: %s", e)

            adapter_fills = getattr(adapter, "_fills_log", [])
            matched = [f for f in adapter_fills if f.client_order_id == secondary_order.client_order_id]
            fills.extend(matched)

        has_fill = any(o.state in (OrderState.FILLED, OrderState.PARTIALLY_FILLED) for o in orders)
        status = ExecutionStatus.EXECUTED if has_fill else ExecutionStatus.FAILED

        logger.info("OCO: Completed for %s, status=%s.", intent.symbol, status.value)
        return self.build_execution_result(intent, orders, fills, status)
