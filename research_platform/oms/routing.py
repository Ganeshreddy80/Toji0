"""Routing Engine determining order routing destinations.
"""

from __future__ import annotations

import uuid
from typing import List

from research_platform.oms.interfaces import IRoutingEngine
from research_platform.oms.models import ExecutionInstruction, Order, RouteDecision


class RoutingEngine(IRoutingEngine):
    """Resolves routing choices mapping orders to execution adapters."""

    def __init__(self, default_exchange: str = "BINANCE") -> None:
        self.default_exchange = default_exchange

    def make_routing_decision(self, order: Order) -> RouteDecision:
        """Decide target destination for order execution."""
        # Simple routing rule: route based on request parameters or default destination
        target = self.default_exchange

        instruction = ExecutionInstruction(
            route_id=str(uuid.uuid4()),
            destination=target,
            display_type="LIMIT" if order.request.order_type == "LIMIT" else "DIRECT"
        )

        return RouteDecision(
            decision_id=str(uuid.uuid4()),
            order_id=order.order_id,
            target_exchange=target,
            instruction=instruction
        )
