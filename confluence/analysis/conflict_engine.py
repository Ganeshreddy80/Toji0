"""Conflict Engine for aggregating and capping conflict penalties."""

from __future__ import annotations

from confluence.core.models import ConflictingFactor


class ConflictEngine:
    """Evaluates and aggregates conflicting factors to calculate the total penalty."""

    def __init__(self, max_penalty: float = 6.0) -> None:
        self._max_penalty = max_penalty

    def calculate_penalty(
        self, conflicting_factors: list[ConflictingFactor]
    ) -> float:
        """Sum the penalties of all conflicting factors, capped at the max penalty."""
        if not conflicting_factors:
            return 0.0

        total_penalty = sum(factor.penalty for factor in conflicting_factors)
        return min(total_penalty, self._max_penalty)
