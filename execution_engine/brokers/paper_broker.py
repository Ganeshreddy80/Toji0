from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from toji_platform.core.types import HealthStatus
from execution_engine.brokers.broker_interface import IBrokerAdapter
from execution_engine.core.enums import OrderState
from execution_engine.core.exceptions import BrokerError
from execution_engine.core.models import Order, OrderFill

from execution_engine.brokers.capabilities import BrokerCapabilities

logger = logging.getLogger(__name__)


class PaperBroker(IBrokerAdapter):
    """Simulates real broker behavior including latency, slippage, commission, timeouts, and partial fills."""

    def get_capabilities(self) -> BrokerCapabilities:
        """Introspect broker advanced execution features and limits."""
        return BrokerCapabilities(
            supports_market=True,
            supports_limit=True,
            supports_stop=True,
            supports_trailing_stop=True,
            supports_reduce_only=True,
            supports_post_only=True,
            supports_oco=True,
            supports_iceberg=True,
            supports_brackets=True,
            supports_twap=True,
            supports_vwap=True,
            max_leverage=20.0,
            precision=4,
            tick_size=0.01,
            min_notional=10.0,
        )

    def __init__(self, config_settings: Dict[str, Any]) -> None:
        self._config = config_settings
        self._connected = False
        
        # In-memory account state
        self._balance = {"USD": float(config_settings.get("initial_balance", 100000.0))}
        self._positions: List[Dict[str, Any]] = []
        self._open_orders: Dict[str, Order] = {}
        self._fills_log: List[OrderFill] = []

    def connect(self) -> None:
        """Establish simulation connection."""
        # Simulate connection latency
        delay = self._config.get("latency_ms", 10.0) / 1000.0
        time.sleep(delay)
        
        # Simulate potential connection drop
        if random.random() < self._config.get("connection_failure_rate", 0.0):
            self._connected = False
            raise BrokerError("PaperBroker: Simulation connection failure.")
            
        self._connected = True

    def disconnect(self) -> None:
        """Terminate connection."""
        self._connected = False

    def health(self) -> HealthStatus:
        """Get health status based on connection state."""
        return HealthStatus.HEALTHY if self._connected else HealthStatus.UNHEALTHY

    def submit_order(self, order: Order) -> Order:
        """Submit and execute order using simulation rules."""
        if not self._connected:
            raise BrokerError("PaperBroker: Order submission failed. Connection is offline.")

        # 1. Simulate API Timeout
        if random.random() < self._config.get("timeout_rate", 0.0):
            timeout = self._config.get("timeout_ms", 1000.0) / 1000.0
            time.sleep(timeout)
            raise BrokerError("PaperBroker: API call timed out.")

        # 2. Simulate API Latency
        delay = self._config.get("latency_ms", 20.0) / 1000.0
        time.sleep(delay)

        # 3. Simulate Order Rejection
        if random.random() < self._config.get("rejection_rate", 0.0):
            rejected_order = order.model_copy(
                update={
                    "state": OrderState.REJECTED,
                    "error_message": "PaperBroker: Order rejected by exchange risk engine.",
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            return rejected_order

        # 4. Process Order State: CREATED/VALIDATED -> SUBMITTED -> ACKNOWLEDGED
        broker_id = f"paper-ord-{random.randint(100000, 999999)}"
        acknowledged_order = order.model_copy(
            update={
                "broker_order_id": broker_id,
                "state": OrderState.ACKNOWLEDGED,
                "updated_at": datetime.now(timezone.utc),
            }
        )

        # 5. Simulate Fill execution
        fill_price = order.price or order.stop_price or 100.0
        
        # Slippage simulation
        slippage_pct = self._config.get("slippage_rate", 0.0005)
        randomized_slippage = random.uniform(0.0, slippage_pct)
        if order.side == "BUY":
            fill_price *= (1.0 + randomized_slippage)
        else:
            fill_price *= (1.0 - randomized_slippage)

        # Commission simulation
        comm_pct = self._config.get("commission_rate", 0.001)
        commission = order.quantity * fill_price * comm_pct

        # Partial Fill vs Full Fill simulation
        if self._config.get("enable_partial_fills", False) and random.random() < 0.3:
            # Partial Fill execution (50% filled)
            qty_filled = order.quantity * 0.5
            final_order = acknowledged_order.model_copy(
                update={
                    "state": OrderState.PARTIALLY_FILLED,
                    "filled_quantity": qty_filled,
                    "average_fill_price": fill_price,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._record_fill(final_order, qty_filled, fill_price, commission * 0.5)
            self._open_orders[order.client_order_id] = final_order
        else:
            # Full Fill execution
            final_order = acknowledged_order.model_copy(
                update={
                    "state": OrderState.FILLED,
                    "filled_quantity": order.quantity,
                    "average_fill_price": fill_price,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._record_fill(final_order, order.quantity, fill_price, commission)
            
            # Update local balance
            total_cost = order.quantity * fill_price
            if order.side == "BUY":
                self._balance["USD"] -= (total_cost + commission)
                # Track position
                self._positions.append({"symbol": order.symbol, "quantity": order.quantity, "entry_price": fill_price})
            else:
                self._balance["USD"] += (total_cost - commission)

        return final_order

    def cancel_order(self, client_order_id: str) -> Order:
        """Cancel working order."""
        if client_order_id in self._open_orders:
            order = self._open_orders.pop(client_order_id)
            cancelled = order.model_copy(
                update={
                    "state": OrderState.CANCELLED,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            return cancelled
        raise BrokerError(f"PaperBroker: Cannot cancel order {client_order_id}. Order not found or already completed.")

    def modify_order(self, client_order_id: str, quantity: float, price: float) -> Order:
        """Modify working order size and limit price."""
        if client_order_id in self._open_orders:
            order = self._open_orders[client_order_id]
            modified = order.model_copy(
                update={
                    "quantity": quantity,
                    "price": price,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._open_orders[client_order_id] = modified
            return modified
        raise BrokerError(f"PaperBroker: Cannot modify order {client_order_id}. Order not found.")

    def get_order(self, client_order_id: str) -> Order:
        """Load simulated order status."""
        if client_order_id in self._open_orders:
            return self._open_orders[client_order_id]
        raise BrokerError(f"PaperBroker: Order {client_order_id} not found.")

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Fetch active open orders."""
        orders = list(self._open_orders.values())
        if symbol:
            orders = [o for o in orders if o.symbol.upper() == symbol.upper()]
        return orders

    def get_positions(self) -> List[Any]:
        """Fetch current positions list."""
        return list(self._positions)

    def get_balance(self) -> dict[str, float]:
        """Fetch cash balance."""
        return dict(self._balance)

    def ping(self) -> bool:
        """Ping check."""
        return self._connected

    def _record_fill(self, order: Order, quantity: float, price: float, commission: float) -> None:
        """Internal helper to log fill logs."""
        fill = OrderFill(
            fill_id=f"fill-{random.randint(100000, 999999)}",
            order_id=order.broker_order_id or "unknown",
            client_order_id=order.client_order_id,
            execution_id=order.execution_id,
            correlation_id=order.correlation_id,
            symbol=order.symbol,
            quantity=quantity,
            price=price,
            commission=commission,
            fee_currency="USD",
            timestamp=datetime.now(timezone.utc),
        )
        self._fills_log.append(fill)
