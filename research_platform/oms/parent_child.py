"""Parent Child Engine partitioning orders into TWAP, Iceberg, and OCO schedules.
"""

from __future__ import annotations

import uuid
from typing import List

from research_platform.oms.models import ChildOrder, Order, OrderRequest, ParentOrder


class ParentChildEngine:
    """Partitions parent orders into child slices."""

    @staticmethod
    def slice_twap(parent: ParentOrder, slices_count: int) -> List[ChildOrder]:
        """Slices total order quantity into equal parts."""
        req = parent.order.request
        qty = req.quantity
        slice_qty = qty / slices_count
        
        children = []
        for i in range(slices_count):
            child_id = f"{parent.parent_id}_child_{i}"
            
            child_req = OrderRequest(
                order_id=child_id,
                symbol=req.symbol,
                direction=req.direction,
                quantity=slice_qty,
                order_type=req.order_type,
                price=req.price,
                time_in_force="IOC",  # typically child orders are IOC/FOK
                strategy_id=req.strategy_id
            )
            child_order = Order(
                order_id=child_id,
                request=child_req,
                status="NEW"
            )
            children.append(
                ChildOrder(
                    child_id=child_id,
                    parent_id=parent.parent_id,
                    order=child_order,
                    sequence_num=i
                )
            )
        return children

    @staticmethod
    def slice_iceberg(parent: ParentOrder, display_qty: float) -> List[ChildOrder]:
        """Slices iceberg order: first child is visible, remainder remains hidden."""
        req = parent.order.request
        qty = req.quantity
        
        if qty <= display_qty:
            # No hidden slicing needed
            slices = [qty]
        else:
            slices = [display_qty, qty - display_qty]

        children = []
        for i, slice_val in enumerate(slices):
            child_id = f"{parent.parent_id}_ice_{i}"
            child_req = OrderRequest(
                order_id=child_id,
                symbol=req.symbol,
                direction=req.direction,
                quantity=slice_val,
                order_type=req.order_type,
                price=req.price,
                time_in_force="IOC",
                strategy_id=req.strategy_id
            )
            child_order = Order(
                order_id=child_id,
                request=child_req,
                status="NEW"
            )
            children.append(
                ChildOrder(
                    child_id=child_id,
                    parent_id=parent.parent_id,
                    order=child_order,
                    sequence_num=i
                )
            )
        return children
