"""Simulated broker managing order creation, validation, and lifecycle state transitions (Sprint 7A)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
from typing import Dict, List, Optional

from backtesting_engine.core.enums import (
    OrderType,
    PositionSide,
    SimulatedOrderStatus,
    TimeInForce,
)
from backtesting_engine.core.events import (
    ExecutionRejected,
    SimulatedOrderCancelled,
    SimulatedOrderPlaced,
)
from backtesting_engine.core.exceptions import SimulatedBrokerError
from backtesting_engine.core.interfaces import ISimulatedBroker
from backtesting_engine.core.models import BacktestConfig, SimulatedOrder
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class SimulatedBroker(ISimulatedBroker):
    """Manages simulated order placements, order statuses, and cancellations offline."""

    def __init__(self, event_bus: Optional[IEventBus] = None) -> None:
        self._orders: Dict[str, SimulatedOrder] = {}
        self._lock = threading.RLock()
        self._event_bus = event_bus

    def place_order(
        self,
        symbol: str,
        side: PositionSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: float = 0.0,
        stop_price: float = 0.0,
        time_in_force: TimeInForce = TimeInForce.GTC,
        config: Optional[BacktestConfig] = None,
    ) -> SimulatedOrder:
        """Create and place a new simulated order with execution constraint validation."""
        if not symbol or quantity <= 0.0:
            raise SimulatedBrokerError("Invalid order parameters: symbol and positive quantity required.")

        if order_type == OrderType.LIMIT and price <= 0.0:
            raise SimulatedBrokerError("LIMIT orders require a positive price.")

        if order_type in (OrderType.STOP, OrderType.STOP_LIMIT) and stop_price <= 0.0:
            raise SimulatedBrokerError("STOP / STOP_LIMIT orders require a positive stop_price.")

        status = SimulatedOrderStatus.ACCEPTED

        # Execution constraints validation if config is provided
        if config:
            rounded_qty = quantity
            if config.lot_size > 0.0:
                rounded_qty = round(round(quantity / config.lot_size) * config.lot_size, config.lot_precision)

            if rounded_qty < config.min_quantity or rounded_qty > config.max_quantity or rounded_qty <= 0.0:
                status = SimulatedOrderStatus.REJECTED
            else:
                quantity = rounded_qty

            # Round price to tick_size multiple
            if config.tick_size > 0.0 and price > 0.0:
                price = round(round(price / config.tick_size) * config.tick_size, config.tick_precision)

            if config.tick_size > 0.0 and stop_price > 0.0:
                stop_price = round(round(stop_price / config.tick_size) * config.tick_size, config.tick_precision)

        now = datetime.now(timezone.utc)
        order = SimulatedOrder(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            order_type=order_type,
            time_in_force=time_in_force,
            status=status,
            created_at=now,
            updated_at=now,
        )

        if status != SimulatedOrderStatus.REJECTED:
            with self._lock:
                self._orders[order.order_id] = order

        if self._event_bus:
            if status == SimulatedOrderStatus.REJECTED:
                self._event_bus.publish(
                    ExecutionRejected(
                        source="backtesting.broker",
                        payload={"order_id": order.order_id, "reason": "Quantity outside min/max constraints"},
                    )
                )
            else:
                self._event_bus.publish(
                    SimulatedOrderPlaced(
                        source="backtesting.broker",
                        payload={"order_id": order.order_id, "symbol": symbol, "side": side.value, "quantity": quantity},
                    )
                )

        logger.info("SimulatedBroker: Placed order %s for %s (%s %f) status=%s", order.order_id, symbol, side.value, quantity, status.value)
        return order

    def cancel_order(self, order_id: str) -> Optional[SimulatedOrder]:
        """Cancel an active simulated order."""
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                return None

            if order.status in (SimulatedOrderStatus.FILLED, SimulatedOrderStatus.CANCELLED, SimulatedOrderStatus.REJECTED):
                return order

            updated = order.model_copy(
                update={
                    "status": SimulatedOrderStatus.CANCELLED,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._orders[order_id] = updated

        if self._event_bus:
            self._event_bus.publish(
                SimulatedOrderCancelled(
                    source="backtesting.broker",
                    payload={"order_id": order_id},
                )
            )

        logger.info("SimulatedBroker: Cancelled order %s", order_id)
        return updated

    def update_order(self, order: SimulatedOrder) -> None:
        """Update an existing order state."""
        with self._lock:
            self._orders[order.order_id] = order

    def get_order(self, order_id: str) -> Optional[SimulatedOrder]:
        """Get an order by ID."""
        with self._lock:
            return self._orders.get(order_id)

    def list_orders(self, status: Optional[SimulatedOrderStatus] = None) -> List[SimulatedOrder]:
        """List simulated orders, optionally filtered by status."""
        with self._lock:
            if status:
                return [o for o in self._orders.values() if o.status == status]
            return list(self._orders.values())
