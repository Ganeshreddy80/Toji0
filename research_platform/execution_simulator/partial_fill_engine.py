"""Partial fill engine simulating incomplete executions.
"""

from __future__ import annotations

from typing import List, Tuple


class PartialFillEngine:
    """Enforces partial matches allocations."""

    def evaluate_fill_ratio(self, quantity: float, available_size: float) -> float:
        if available_size <= 0.0:
            return 0.0
        return min(1.0, available_size / quantity)
