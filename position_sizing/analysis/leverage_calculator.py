"""Leverage Calculator for determining safe and required leverage."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LeverageCalculator:
    """Computes and validates required leverage against safe limits."""

    def calculate_leverage(
        self,
        quantity: float,
        entry_price: float,
        balance: float,
        max_leverage_limit: float = 10.0,
        **kwargs: Any,
    ) -> dict[str, float]:
        """Determine leverage parameters.

        Returns a dictionary containing:
            required_leverage: Leverage needed to open the position.
            safe_leverage: The maximum leverage limit considered safe.
            max_allowed_leverage: Hard limit set by config or broker.
        """
        if balance <= 0:
            return {
                "required_leverage": 1.0,
                "safe_leverage": 1.0,
                "max_allowed_leverage": max_leverage_limit,
            }

        position_value = quantity * entry_price
        required_leverage = position_value / balance

        # Safe leverage is typically configured as a conservative limit (e.g., 70% of max broker leverage)
        safe_leverage = max(1.0, max_leverage_limit * 0.7)

        return {
            "required_leverage": required_leverage,
            "safe_leverage": safe_leverage,
            "max_allowed_leverage": max_leverage_limit,
        }
