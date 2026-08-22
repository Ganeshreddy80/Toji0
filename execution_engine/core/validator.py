from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from execution_engine.core.exceptions import ValidationError
from execution_engine.core.interfaces import IExecutionStateStore, IOrderValidator
from execution_engine.core.models import ExecutionConfig, ExecutionRequest

logger = logging.getLogger(__name__)


class ExecutionDeduplicator:
    """Thread-safe request cache mapping processed request IDs to guarantee exactly-once processing."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processed_requests: set[str] = set()

    def is_duplicate(self, request_id: str) -> bool:
        """Check if request_id has already been processed by the engine."""
        with self._lock:
            return request_id in self._processed_requests

    def register_request(self, request_id: str) -> None:
        """Mark a request_id as processed."""
        with self._lock:
            self._processed_requests.add(request_id)

    def check_and_register(self, request_id: str) -> bool:
        """Atomic check and register. Returns True if registered successfully (not a duplicate), False otherwise."""
        with self._lock:
            if request_id in self._processed_requests:
                return False
            self._processed_requests.add(request_id)
            return True

    def clear(self) -> None:
        """Reset the deduplication cache."""
        with self._lock:
            self._processed_requests.clear()


class ExecutionValidator(IOrderValidator):
    """Executes pre-trade validation checks against capital constraints and broker rules."""

    def __init__(self, config: ExecutionConfig, deduplicator: ExecutionDeduplicator) -> None:
        self._config = config
        self._deduplicator = deduplicator

    def validate_request(self, request: ExecutionRequest, state_store: IExecutionStateStore) -> list[str]:
        """Perform comprehensive pre-trade validation checks.

        Returns:
            list[str]: Descriptions of any validation rule violations.
        """
        violations: list[str] = []

        # 0. Mandatory Field Presence & Positivity Checks
        if not request.symbol or not request.symbol.strip():
            violations.append("Invalid request: Symbol must be non-empty.")

        if request.quantity <= 0:
            violations.append(f"Invalid quantity: Order quantity must be positive, received {request.quantity}.")

        from execution_engine.core.enums import OrderType
        if request.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and (request.price is None or request.price <= 0):
            violations.append(f"Invalid price: Order type {request.order_type.value} requires a positive limit price.")

        if request.order_type in (OrderType.STOP_MARKET, OrderType.STOP_LIMIT) and (request.stop_price is None or request.stop_price <= 0):
            violations.append(f"Invalid stop price: Order type {request.order_type.value} requires a positive stop price.")

        if violations:
            return violations

        # 1. Deduplication Check
        if not self._deduplicator.check_and_register(request.request_id):
            violations.append(f"Duplicate execution: request_id '{request.request_id}' has already been processed.")
            return violations

        # 2. Maximum Order Age (Stale Signal) Check
        now = datetime.now(timezone.utc)
        age_seconds = (now - request.timestamp).total_seconds()
        # Fetch max age limit from configuration (default to 60s)
        max_age = self._config.paper_broker_settings.get("max_order_age_seconds", 60.0)
        if age_seconds > max_age:
            violations.append(f"Stale signal: request age is {age_seconds:.1f}s, exceeding maximum allowed age of {max_age}s.")

        # 3. Minimum Quantity Check
        min_qty = self._config.min_notional_rules.get(request.symbol.upper(), 0.001)
        if request.quantity < min_qty:
            violations.append(f"Minimum quantity violation: request quantity {request.quantity} is less than minimum {min_qty} for {request.symbol}.")

        # 4. Minimum Notional Check — NEVER rely on a fabricated default price fallback (e.g. 1.0)
        estimated_price = request.price or request.stop_price
        if estimated_price is not None and estimated_price > 0:
            notional_value = request.quantity * estimated_price
            min_notional = self._config.min_notional_rules.get(f"{request.symbol.upper()}_NOTIONAL", 10.0)
            if notional_value < min_notional:
                violations.append(
                    f"Minimum notional violation: order value ${notional_value:.2f} is less than minimum notional ${min_notional:.2f}."
                )

        # 5. Quantity Precision Check
        precision = self._config.precision_rules.get(request.symbol.upper(), {}).get("quantity", 4)
        qty_str = f"{request.quantity:.8f}".rstrip("0")
        decimal_places = len(qty_str.split(".")[1]) if "." in qty_str else 0
        if decimal_places > precision:
            violations.append(
                f"Quantity precision violation: order precision {decimal_places} exceeds maximum permitted {precision} for {request.symbol}."
            )

        # 6. Price Step / Tick Size Check
        if request.price:
            tick_size = self._config.tick_size_rules.get(request.symbol.upper(), 0.01)
            # Check price aligns with tick size steps (avoiding float division errors)
            remainder = round(request.price % tick_size, 8)
            if remainder != 0.0 and remainder != tick_size:
                violations.append(
                    f"Tick size violation: price {request.price} does not align with tick size {tick_size} for {request.symbol}."
                )

        return violations
