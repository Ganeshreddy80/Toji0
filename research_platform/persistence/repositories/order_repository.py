"""PostgreSQL order repository wrapper.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_platform.persistence.postgres.base_repository import BaseRepository
from research_platform.persistence.postgres.migrations import OrderModel
from research_platform.oms.models import Order, Fill


class PostgresOrderRepository(BaseRepository):
    """PostgreSQL-backed OMS repository implementation."""

    def __init__(self, session_manager) -> None:
        super().__init__(session_manager, OrderModel)

    def save_order(self, order: Order) -> None:
        model = self.get(order.order_id)
        if model:
            updates = {
                "strategy_id": order.strategy_id,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.quantity,
                "price": order.price,
                "order_type": order.order_type,
                "status": order.status
            }
            self.update(order.order_id, updates)
        else:
            new_model = OrderModel(
                order_id=order.order_id,
                strategy_id=order.strategy_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=order.price,
                order_type=order.order_type,
                status=order.status
            )
            self.create(new_model)

    def get_order(self, order_id: str) -> Optional[Order]:
        model = self.get(order_id)
        if model:
            return Order(
                order_id=model.order_id,
                strategy_id=model.strategy_id,
                symbol=model.symbol,
                side=model.side,
                quantity=model.quantity,
                price=model.price,
                order_type=model.order_type,
                status=model.status
            )
        return None

    def list_orders(self, status: Optional[str] = None) -> List[Order]:
        filters = {}
        if status:
            filters["status"] = status
        models = self.list_all(filters=filters)
        return [
            Order(
                order_id=m.order_id,
                strategy_id=m.strategy_id,
                symbol=m.symbol,
                side=m.side,
                quantity=m.quantity,
                price=m.price,
                order_type=m.order_type,
                status=m.status
            )
            for m in models
        ]
