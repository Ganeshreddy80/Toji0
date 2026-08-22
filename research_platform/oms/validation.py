"""Validation Engine auditing order parameters bounds.
"""

from __future__ import annotations

from typing import Dict, Set

from research_platform.oms.interfaces import IOrderValidator
from research_platform.oms.models import OrderRequest


class OrderValidator(IOrderValidator):
    """Enforces order tick step increments, minimum lot sizes, and duplicate filters."""

    def __init__(
        self,
        min_qty: float = 0.001,
        max_qty: float = 1000.0,
        tick_size: float = 0.01,
        lot_size: float = 0.001
    ) -> None:
        self.min_qty = min_qty
        self.max_qty = max_qty
        self.tick_size = tick_size
        self.lot_size = lot_size
        self._received_ids: Set[str] = set()

    def validate_order(self, request: OrderRequest) -> bool:
        """Verify order sizes, price ticks, and lot bounds.

        Raises:
            ValueError: If validation parameters fail.
        """
        # 1. Duplicate order check
        if request.order_id in self._received_ids:
            raise ValueError(f"Duplicate order ID detected: {request.order_id}")
        self._received_ids.add(request.order_id)

        # 2. Quantity checks
        if request.quantity < self.min_qty:
            raise ValueError(f"Order quantity {request.quantity} falls below min limit {self.min_qty}")
        if request.quantity > self.max_qty:
            raise ValueError(f"Order quantity {request.quantity} exceeds max limit {self.max_qty}")

        # 3. Lot size alignment
        # Check if quantity is a multiple of lot size (using small epsilon for floating-point modulo)
        rem_qty = request.quantity % self.lot_size
        if not (rem_qty < 1e-9 or abs(rem_qty - self.lot_size) < 1e-9):
            raise ValueError(f"Order quantity {request.quantity} is not a multiple of lot size {self.lot_size}")

        # 4. Tick size alignment for pricing (if limit order)
        if request.order_type in ("LIMIT", "STOP_LIMIT") and request.price > 0.0:
            rem_price = request.price % self.tick_size
            if not (rem_price < 1e-9 or abs(rem_price - self.tick_size) < 1e-9):
                raise ValueError(f"Order price {request.price} is not a multiple of tick size {self.tick_size}")

        return True
