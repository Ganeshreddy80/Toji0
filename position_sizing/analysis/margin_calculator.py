"""Margin Calculator for evaluating margins and utilization."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MarginCalculator:
    """Computes required margin and free margin metrics."""

    def calculate_margin(
        self,
        quantity: float,
        entry_price: float,
        leverage: float,
        balance: float,
        free_margin_ratio: float = 1.0,
        **kwargs: Any,
    ) -> dict[str, float]:
        """Compute margin parameters.

        Returns a dictionary containing:
            required_margin: Estimated margin required to hold the position.
            available_margin: Total margin capacity.
            free_margin: Remaining margin after this position is opened.
            margin_utilization: The fraction of account balance used for margin.
        """
        position_value = quantity * entry_price
        required_margin = position_value / max(1.0, leverage)
        
        # Available margin = balance * free_margin_ratio
        available_margin = balance * free_margin_ratio
        free_margin = max(0.0, available_margin - required_margin)
        
        margin_utilization = 0.0
        if balance > 0:
            margin_utilization = required_margin / balance

        return {
            "required_margin": required_margin,
            "available_margin": available_margin,
            "free_margin": free_margin,
            "margin_utilization": margin_utilization,
        }
