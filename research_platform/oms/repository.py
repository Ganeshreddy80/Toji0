"""Thread-safe repository for OMS orders, fills, and histories with PostgreSQL delegation.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.oms.interfaces import IOMSRepository
from research_platform.oms.models import Fill, Order, OrderAudit, ParentOrder, ChildOrder
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.order_repository import PostgresOrderRepository


class OMSRepository(IOMSRepository):
    """Memory-backed, thread-safe repository with PostgreSQL delegation capabilities."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._orders: Dict[str, Order] = {}
        self._fills: List[Fill] = []
        self._history: Dict[str, List[str]] = {}
        self._audits: Dict[str, List[OrderAudit]] = {}
        self._parents: Dict[str, ParentOrder] = {}
        self._children: Dict[str, ChildOrder] = {}

    def _get_pg_repo(self) -> Optional[PostgresOrderRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresOrderRepository(session_manager)
        return None

    def save_order(self, order: Order) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_order(order)
            
        with self._lock:
            self._orders[order.order_id] = order
            if order.order_id not in self._history:
                self._history[order.order_id] = []
            self._history[order.order_id].append(order.status)

    def get_order(self, order_id: str) -> Optional[Order]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_order(order_id)
            
        with self._lock:
            return self._orders.get(order_id)

    def list_orders(self, status: Optional[str] = None) -> List[Order]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.list_orders(status)
            
        with self._lock:
            vals = list(self._orders.values())
            if status:
                return [o for o in vals if o.status == status]
            return vals

    def save_fill(self, fill: Fill) -> None:
        with self._lock:
            self._fills.append(fill)

    def list_fills(self, order_id: Optional[str] = None) -> List[Fill]:
        with self._lock:
            if order_id:
                return [f for f in self._fills if f.order_id == order_id]
            return list(self._fills)

    def get_order_history(self, order_id: str) -> List[str]:
        with self._lock:
            return list(self._history.get(order_id, []))

    def get_queue_depth(self) -> dict[str, int]:
        """Return length counts of the various order status categories."""
        orders = self.list_orders()
        depths = {
            "NEW": 0,
            "VALIDATED": 0,
            "QUEUED": 0,
            "ROUTED": 0,
            "FILLED": 0,
            "CANCELLED": 0,
            "REJECTED": 0
        }
        for o in orders:
            if o.status in depths:
                depths[o.status] += 1
        return depths

    def save_audit(self, audit: OrderAudit) -> None:
        with self._lock:
            self._audits.setdefault(audit.order_id, []).append(audit)

    def save_parent(self, parent: ParentOrder) -> None:
        with self._lock:
            self._parents[parent.parent_id] = parent

    def save_child(self, child: ChildOrder) -> None:
        with self._lock:
            self._children[child.child_id] = child


OrderRepository = OMSRepository


