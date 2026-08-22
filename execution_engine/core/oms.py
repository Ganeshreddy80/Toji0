import threading
from typing import Dict, List, Optional, Any
import logging
from execution_engine.core.enums import OrderState
from execution_engine.core.models import Order, OrderFill
from execution_engine.brokers.broker_interface import IBrokerAdapter

logger = logging.getLogger(__name__)


class OrderManager:
    """Manages the full lifecycle and categorization of trade orders."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._orders: Dict[str, Order] = {}

    def add_order(self, order: Order) -> None:
        with self._lock:
            self._orders[order.client_order_id] = order

    def update_order(self, order: Order) -> None:
        with self._lock:
            self._orders[order.client_order_id] = order

    def get_order(self, client_order_id: str) -> Optional[Order]:
        with self._lock:
            return self._orders.get(client_order_id)

    def get_all_orders(self) -> List[Order]:
        with self._lock:
            return list(self._orders.values())

    def get_open_orders(self) -> List[Order]:
        with self._lock:
            open_states = (
                OrderState.CREATED,
                OrderState.VALIDATED,
                OrderState.QUEUED,
                OrderState.SUBMITTED,
                OrderState.ACKNOWLEDGED,
                OrderState.PARTIALLY_FILLED,
            )
            return [o for o in self._orders.values() if o.state in open_states]

    def get_completed_orders(self) -> List[Order]:
        with self._lock:
            return [o for o in self._orders.values() if o.state == OrderState.FILLED]

    def get_cancelled_orders(self) -> List[Order]:
        with self._lock:
            return [o for o in self._orders.values() if o.state == OrderState.CANCELLED]

    def get_rejected_orders(self) -> List[Order]:
        with self._lock:
            return [o for o in self._orders.values() if o.state == OrderState.REJECTED]

    def get_expired_orders(self) -> List[Order]:
        with self._lock:
            return [o for o in self._orders.values() if o.state == OrderState.EXPIRED]


class FillManager:
    """Tracks order executions, fills logs, average entry prices, and commission details."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._fills: List[OrderFill] = []
        self._positions: Dict[str, float] = {}

    def add_fill(self, fill: OrderFill) -> None:
        with self._lock:
            self._fills.append(fill)

    def get_fills_for_order(self, order_id: str) -> List[OrderFill]:
        with self._lock:
            return [f for f in self._fills if f.order_id == order_id or f.client_order_id == order_id]

    def get_total_commission(self, fee_currency: str = "USD") -> float:
        with self._lock:
            return sum(f.commission for f in self._fills if f.fee_currency == fee_currency)

    def get_all_fills(self) -> List[OrderFill]:
        with self._lock:
            return list(self._fills)


class BrokerManager:
    """Manages active registration and connection monitoring of multiple broker adapters."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._adapters: Dict[str, IBrokerAdapter] = {}

    def register_broker(self, broker_id: str, adapter: IBrokerAdapter) -> None:
        with self._lock:
            self._adapters[broker_id.lower()] = adapter

    def get_broker(self, broker_id: str) -> Optional[IBrokerAdapter]:
        with self._lock:
            return self._adapters.get(broker_id.lower())

    def get_all_brokers(self) -> Dict[str, IBrokerAdapter]:
        with self._lock:
            return dict(self._adapters)


class ExecutionManager:
    """Coordinates execution requests and FSM updates across OMS managers."""

    def __init__(self, order_mgr: OrderManager, fill_mgr: FillManager, broker_mgr: BrokerManager) -> None:
        self.order_manager = order_mgr
        self.fill_manager = fill_mgr
        self.broker_manager = broker_mgr
        self._lock = threading.Lock()

    def process_order_update(self, order: Order) -> None:
        with self._lock:
            self.order_manager.update_order(order)
            logger.info("ExecutionManager: Order %s updated to state %s", order.client_order_id, order.state)
