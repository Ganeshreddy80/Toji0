"""Order Engine managing order lifecycle, validation, and status state transitions (Sprint 9A)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
from typing import Dict, List, Optional

from paper_trading.models.paper_models import (
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
)

logger = logging.getLogger(__name__)


class PaperOrderEngine:
    """Thread-safe order engine handling order validation, lifecycle, and state transitions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._orders: Dict[str, PaperOrder] = {}

    def create_order(
        self,
        symbol: str,
        side: PaperOrderSide,
        quantity: float,
        order_type: PaperOrderType = PaperOrderType.MARKET,
        limit_price: float = 0.0,
        stop_price: float = 0.0,
        order_id: Optional[str] = None,
    ) -> PaperOrder:
        """Create and register a new paper order object."""
        if quantity <= 0.0:
            raise ValueError(f"Order quantity must be positive, got {quantity}")

        if order_type == PaperOrderType.LIMIT and limit_price <= 0.0:
            raise ValueError("LIMIT order requires limit_price > 0")

        if order_type == PaperOrderType.STOP and stop_price <= 0.0:
            raise ValueError("STOP order requires stop_price > 0")

        now = datetime.now(timezone.utc)
        kwargs = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "limit_price": limit_price,
            "stop_price": stop_price,
            "status": PaperOrderStatus.NEW,
            "submitted_at": now,
            "updated_at": now,
        }
        if order_id:
            with self._lock:
                if order_id in self._orders:
                    raise ValueError(f"Duplicate order protection: Order ID {order_id} already exists.")
            kwargs["order_id"] = order_id

        order = PaperOrder(**kwargs)

        with self._lock:
            if order.order_id in self._orders:
                raise ValueError(f"Duplicate order protection: Order ID {order.order_id} already exists.")
            self._orders[order.order_id] = order
            return order

    def update_order_status(
        self,
        order_id: str,
        new_status: PaperOrderStatus,
        filled_qty: Optional[float] = None,
        avg_fill_price: Optional[float] = None,
    ) -> PaperOrder:
        """Transition order to a new status state."""
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                raise ValueError(f"Order ID {order_id} not found.")

            curr_filled = filled_qty if filled_qty is not None else order.filled_quantity
            curr_avg_price = avg_fill_price if avg_fill_price is not None else order.average_fill_price

            updated_order = PaperOrder(
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
                limit_price=order.limit_price,
                stop_price=order.stop_price,
                status=new_status,
                filled_quantity=curr_filled,
                average_fill_price=curr_avg_price,
                submitted_at=order.submitted_at,
                updated_at=datetime.now(timezone.utc),
            )
            self._orders[order_id] = updated_order
            return updated_order

    def get_order(self, order_id: str) -> Optional[PaperOrder]:
        """Get order by ID."""
        with self._lock:
            return self._orders.get(order_id)

    def get_active_orders(self) -> List[PaperOrder]:
        """Get all pending/partially filled active orders."""
        with self._lock:
            active_statuses = {PaperOrderStatus.NEW, PaperOrderStatus.PENDING, PaperOrderStatus.PARTIALLY_FILLED}
            return [o for o in self._orders.values() if o.status in active_statuses]

    def cancel_order(self, order_id: str) -> PaperOrder:
        """Cancel an active order."""
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                raise ValueError(f"Order ID {order_id} not found.")

            if order.status in (PaperOrderStatus.FILLED, PaperOrderStatus.CANCELLED, PaperOrderStatus.REJECTED):
                raise ValueError(f"Cannot cancel order in terminal state {order.status}.")

            return self.update_order_status(order_id, PaperOrderStatus.CANCELLED)
