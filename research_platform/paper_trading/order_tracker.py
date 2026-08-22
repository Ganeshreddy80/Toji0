"""Order tracker monitoring active, filled, and cancelled states.
"""

from __future__ import annotations

import logging
from typing import Dict
from research_platform.paper_trading.models import PaperOrder

logger = logging.getLogger(__name__)


class OrderTracker:
    """Tracks submission status for sandbox trade orders."""

    def __init__(self) -> None:
        self._orders: Dict[str, PaperOrder] = {}

    def track_order(self, order: PaperOrder) -> None:
        self._orders[order.order_id] = order

    def update_order_status(self, order_id: str, status: str, executed_price: float = 0.0, executed_qty: float = 0.0) -> PaperOrder:
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order '{order_id}' not tracked.")
            
        updated = order.model_copy(update={
            "status": status,
            "executed_price": executed_price if executed_price > 0.0 else order.executed_price,
            "executed_quantity": executed_qty if executed_qty > 0.0 else order.executed_quantity
        })
        self._orders[order_id] = updated
        return updated
