"""Order State Machine transition validations.
"""

from __future__ import annotations

from typing import Dict, Set

from research_platform.oms.interfaces import IOrderStateMachine
from research_platform.oms.models import Order


class OrderStateMachine(IOrderStateMachine):
    """Enforces institutional status transition path rules."""

    # Map allowed next states for each state
    _ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
        "NEW": {"VALIDATED", "REJECTED"},
        "VALIDATED": {"ROUTED", "REJECTED"},
        "ROUTED": {"PENDING", "REJECTED"},
        "PENDING": {"PARTIALLY_FILLED", "FILLED", "CANCELLED", "EXPIRED", "REPLACED"},
        "PARTIALLY_FILLED": {"PARTIALLY_FILLED", "FILLED", "CANCELLED", "EXPIRED"},
        "FILLED": {"SETTLED"},
        "SETTLED": set(),
        "REJECTED": set(),
        "CANCELLED": set(),
        "EXPIRED": set(),
        "REPLACED": {"PENDING", "ROUTED"}
    }

    def transition(self, order: Order, new_status: str) -> Order:
        """Transition order to new status, validating paths.

        Raises:
            ValueError: If the transition path is invalid.
        """
        curr = order.status
        allowed = self._ALLOWED_TRANSITIONS.get(curr, set())

        if new_status not in allowed:
            raise ValueError(f"Illegal state machine transition from {curr} to {new_status}")

        # Preserve all attributes of the order when transitioning status
        try:
            return order.model_copy(update={"status": new_status})
        except AttributeError:
            return order.copy(update={"status": new_status})

