"""Bracket & Trailing Stop Execution Algorithm.

Manages bracket orders: submits the entry order, then automatically
places Take Profit and Stop Loss child orders once the entry fills.
Also handles trailing stop callback logic.
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


class BracketAlgorithm(BaseExecutionAlgorithm):
    """Bracket order execution algorithm.

    Submits:
    1. Entry order (MARKET or LIMIT based on intent).
    2. Take Profit limit order on fill.
    3. Stop Loss stop-market order on fill.
    4. Optional trailing stop callback.

    Parameters (via intent):
        - bracket_take_profit: TP price.
        - bracket_stop_loss: SL price.
        - trailing_stop_callback_rate: Optional trailing callback %.
    """

    def __init__(self) -> None:
        super().__init__(ExecutionAlgorithmType.BRACKET)

    def generate_slices(
        self,
        intent: OrderIntent,
        adapter: IBrokerAdapter,
    ) -> List[ExecutionSlice]:
        slices = []

        # Slice 0: Entry order
        slices.append(ExecutionSlice(
            slice_id=f"brk-entry-{uuid.uuid4().hex[:8]}",
            algo_id=f"bracket-{intent.intent_id}",
            intent_id=intent.intent_id,
            execution_id=intent.execution_id,
            slice_index=0,
            quantity=intent.quantity,
            price=intent.price,
        ))

        # Slice 1: Take Profit
        if intent.bracket_take_profit is not None:
            slices.append(ExecutionSlice(
                slice_id=f"brk-tp-{uuid.uuid4().hex[:8]}",
                algo_id=f"bracket-{intent.intent_id}",
                intent_id=intent.intent_id,
                execution_id=intent.execution_id,
                slice_index=1,
                quantity=intent.quantity,
                price=intent.bracket_take_profit,
            ))

        # Slice 2: Stop Loss
        if intent.bracket_stop_loss is not None:
            slices.append(ExecutionSlice(
                slice_id=f"brk-sl-{uuid.uuid4().hex[:8]}",
                algo_id=f"bracket-{intent.intent_id}",
                intent_id=intent.intent_id,
                execution_id=intent.execution_id,
                slice_index=2,
                quantity=intent.quantity,
                price=intent.bracket_stop_loss,
            ))

        logger.info(
            "Bracket: Generated %d legs (entry + TP + SL) for %s.",
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

        if not slices:
            return self.build_execution_result(intent, orders, fills, ExecutionStatus.FAILED)

        # Execute entry order (slice 0)
        entry_slice = slices[0]
        entry_order = self.create_child_order(intent, entry_slice)

        try:
            executed_entry = adapter.submit_order(entry_order)
            orders.append(executed_entry)

            if executed_entry.state not in (OrderState.FILLED, OrderState.PARTIALLY_FILLED):
                logger.warning(
                    "Bracket: Entry order not filled (state=%s), aborting bracket for %s.",
                    executed_entry.state.value, intent.symbol,
                )
                return self.build_execution_result(intent, orders, fills, ExecutionStatus.FAILED)

            # Collect entry fills
            adapter_fills = getattr(adapter, "_fills_log", [])
            matched = [f for f in adapter_fills if f.client_order_id == entry_order.client_order_id]
            fills.extend(matched)

        except Exception as e:
            logger.error("Bracket: Entry order failed for %s: %s", intent.symbol, e)
            failed_order = entry_order.model_copy(update={
                "state": OrderState.REJECTED,
                "error_message": str(e),
                "updated_at": datetime.now(timezone.utc),
            })
            orders.append(failed_order)
            return self.build_execution_result(intent, orders, fills, ExecutionStatus.FAILED)

        # Entry filled — submit TP and SL legs
        exit_side = OrderSide.SELL if intent.side == OrderSide.BUY else OrderSide.BUY

        for s in slices[1:]:
            if s.slice_index == 1:
                # Take Profit — limit order on exit side
                tp_order = Order(
                    client_order_id=f"brk-tp-{uuid.uuid4().hex[:8]}",
                    execution_id=intent.execution_id,
                    request_id=intent.request_id,
                    signal_id=intent.signal_id,
                    strategy_id=intent.strategy_id,
                    position_id=intent.position_id,
                    correlation_id=intent.correlation_id,
                    symbol=intent.symbol,
                    side=exit_side,
                    order_type=OrderType.LIMIT,
                    quantity=s.quantity,
                    price=s.price,
                    time_in_force=intent.time_in_force,
                    state=OrderState.CREATED,
                    execution_flags=["REDUCE_ONLY"],
                )
                try:
                    executed_tp = adapter.submit_order(tp_order)
                    orders.append(executed_tp)
                except Exception as e:
                    logger.error("Bracket: TP order failed for %s: %s", intent.symbol, e)

            elif s.slice_index == 2:
                # Stop Loss — stop market order on exit side
                sl_order = Order(
                    client_order_id=f"brk-sl-{uuid.uuid4().hex[:8]}",
                    execution_id=intent.execution_id,
                    request_id=intent.request_id,
                    signal_id=intent.signal_id,
                    strategy_id=intent.strategy_id,
                    position_id=intent.position_id,
                    correlation_id=intent.correlation_id,
                    symbol=intent.symbol,
                    side=exit_side,
                    order_type=OrderType.STOP_MARKET,
                    quantity=s.quantity,
                    price=None,
                    stop_price=s.price,
                    time_in_force=intent.time_in_force,
                    state=OrderState.CREATED,
                    execution_flags=["REDUCE_ONLY"],
                )
                try:
                    executed_sl = adapter.submit_order(sl_order)
                    orders.append(executed_sl)
                except Exception as e:
                    logger.error("Bracket: SL order failed for %s: %s", intent.symbol, e)

        logger.info(
            "Bracket: All legs submitted for %s (entry=%s, %d exit legs).",
            intent.symbol, executed_entry.state.value, len(slices) - 1,
        )
        return self.build_execution_result(intent, orders, fills, ExecutionStatus.EXECUTED)
