"""Abstract contracts for the Institutional Order Management System (OMS).
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional
from research_platform.oms.models import (
    Fill,
    Order,
    OrderState,
    OrderHistory,
    ExecutionReport,
    OrderRequest,
    OrderExecutionPlan,
    RouteDecision,
)


class IOMSRepository(abc.ABC):
    """Abstract contract for persistent caching of orders, histories, and fills."""

    @abc.abstractmethod
    def save_order(self, order: Order) -> None:
        """Persist an order state snapshot."""

    @abc.abstractmethod
    def get_order(self, order_id: str) -> Optional[Order]:
        """Retrieve order details by ID."""

    @abc.abstractmethod
    def list_orders(self, status: Optional[str] = None) -> List[Order]:
        """List orders filtering by status state."""

    @abc.abstractmethod
    def save_fill(self, fill: Fill) -> None:
        """Persist a fill execution."""

    @abc.abstractmethod
    def list_fills(self, order_id: Optional[str] = None) -> List[Fill]:
        """List fills matching filter bounds."""


class IOMS(abc.ABC):
    """Abstract contract for core OMS orchestrators."""

    @abc.abstractmethod
    def submit_order(
        self,
        strategy_id: str,
        symbol: str,
        quantity: float,
        price: float,
        order_type: str,
        side: str,
        rationale: str
    ) -> Order:
        """Process strategy orders execution, validate parameters, and evaluate risk bounds."""


class IOrderRouter(abc.ABC):
    """Abstract contract for execution adapter routers."""

    @abc.abstractmethod
    def route_order(self, order: Order, rationale: str) -> Order:
        """Send orders to downstream brokers or paper routers."""


class IExecutionTracker(abc.ABC):
    """Abstract contract for receiving execution logs callbacks."""

    @abc.abstractmethod
    def handle_execution_report(self, report: ExecutionReport) -> None:
        """Process execution updates, migrating orders states and storing fills."""
class IOMSRepresentation:
    pass


class IOrderValidator(abc.ABC):
    @abc.abstractmethod
    def validate_order(self, request: OrderRequest) -> bool:
        """Validate an order request."""


class IExecutionPlanner(abc.ABC):
    @abc.abstractmethod
    def generate_plan(self, parent_id: str, quantity: float, intervals: int) -> OrderExecutionPlan:
        """Generate a sliced order execution plan."""


class IRoutingEngine(abc.ABC):
    @abc.abstractmethod
    def make_routing_decision(self, order: Order) -> RouteDecision:
        """Make routing decision for the order."""


class IOrderStateMachine(abc.ABC):
    @abc.abstractmethod
    def transition(self, order: Order, new_status: str) -> Order:
        """Transition order to new status."""

