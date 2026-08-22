"""Stress Testing engine simulating shifts in volatility.
"""

from __future__ import annotations

import numpy as np

from research_platform.risk_management.models import StressScenario, StressTestResult


class StressTestingEngine:
    """Simulates portfolio metrics shifts under extreme market regimes."""

    def __init__(self, loss_limit: float = 20000.0) -> None:
        self.loss_limit = loss_limit

    def run_stress_test(
        self,
        returns: np.ndarray,
        scenario: StressScenario,
        portfolio_value: float = 100000.0
    ) -> StressTestResult:
        """Estimate portfolio returns shifts under stress multipliers."""
        if len(returns) < 2:
            return StressTestResult(
                scenario_name=scenario.scenario_name,
                expected_loss=0.0,
                passed=True
            )

        # Standard loss estimation: shift standard deviation * volatility_shift multiplier
        vol = np.std(returns)
        shifted_vol = vol * scenario.volatility_shift
        expected_loss = portfolio_value * 2.0 * shifted_vol  # 2 standard deviation loss

        passed = expected_loss <= self.loss_limit

        return StressTestResult(
            scenario_name=scenario.scenario_name,
            expected_loss=expected_loss,
            passed=passed
        )
