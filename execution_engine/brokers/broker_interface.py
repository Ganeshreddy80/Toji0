from __future__ import annotations

from typing import Any, List, Optional, Protocol

from toji_platform.core.types import HealthStatus
from execution_engine.core.models import Order
from execution_engine.brokers.capabilities import BrokerCapabilities


class IBrokerAdapter(Protocol):
    """Protocol defining the standard interface for external broker and exchange adapters."""

    def get_capabilities(self) -> BrokerCapabilities:
        """Introspect broker advanced execution features and limits."""
        ...

    def connect(self) -> None:
        """Establish connection with the exchange / broker API endpoints."""
        ...

    def disconnect(self) -> None:
        """Gracefully disconnect from the exchange / broker API."""
        ...

    def health(self) -> HealthStatus:
        """Retrieve active connectivity health status."""
        ...

    def submit_order(self, order: Order) -> Order:
        """Submit a new order to the broker.

        Returns:
            Order: The updated order state containing broker_order_id and state updates.
        """
        ...

    def cancel_order(self, client_order_id: str) -> Order:
        """Cancel an active order.

        Returns:
            Order: The updated order state marked as CANCELLED.
        """
        ...

    def modify_order(self, client_order_id: str, quantity: float, price: float) -> Order:
        """Modify quantity or price of a working order."""
        ...

    def get_order(self, client_order_id: str) -> Order:
        """Query the broker for the current state of a specific order."""
        ...

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Fetch all currently active working orders."""
        ...

    def get_positions(self) -> List[Any]:
        """Fetch current open position sizes and values."""
        ...

    def get_balance(self) -> dict[str, float]:
        """Fetch account balances."""
        ...

    def ping(self) -> bool:
        """Check connection latency or alive status.

        Returns:
            bool: True if broker responds, False if timed out or disconnected.
        """
        ...
