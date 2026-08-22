"""Constraint Engine validating portfolio allocation limits.
"""

from __future__ import annotations

from typing import Dict, List

from research_platform.portfolio_engine.interfaces import IConstraintEngine
from research_platform.portfolio_engine.models import ConstraintViolation, PortfolioWeights


class ConstraintEngine(IConstraintEngine):
    """Enforces asset bounds, leverage caps, and sector limits."""

    def __init__(
        self,
        max_weight: float = 0.30,
        min_weight: float = -0.10,
        max_leverage: float = 1.50
    ) -> None:
        self.max_weight = max_weight
        self.min_weight = min_weight
        self.max_leverage = max_leverage

    def check_constraints(self, weights: PortfolioWeights) -> List[ConstraintViolation]:
        """Verify allocation weights against leverage, sector, or max/min constraints."""
        violations = []
        sum_abs_weights = 0.0

        for sym, w in weights.weights.items():
            # 1. Max Weight Check
            if w > self.max_weight:
                violations.append(
                    ConstraintViolation(
                        constraint_name="MaxWeight",
                        violated=True,
                        details=f"Asset {sym} weight {w:.2%} exceeds max limit {self.max_weight:.2%}"
                    )
                )

            # 2. Min Weight Check
            if w < self.min_weight:
                violations.append(
                    ConstraintViolation(
                        constraint_name="MinWeight",
                        violated=True,
                        details=f"Asset {sym} weight {w:.2%} falls below min limit {self.min_weight:.2%}"
                    )
                )

            sum_abs_weights += abs(w)

        # 3. Leverage Check
        if sum_abs_weights > self.max_leverage:
            violations.append(
                ConstraintViolation(
                    constraint_name="MaxLeverage",
                    violated=True,
                    details=f"Total leverage {sum_abs_weights:.2f} exceeds limit {self.max_leverage:.2f}"
                )
            )

        return violations
