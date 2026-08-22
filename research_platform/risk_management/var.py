"""Value-at-Risk Engine calculating parametric and historical metrics.
"""

from __future__ import annotations

import numpy as np
from datetime import datetime, timezone

from research_platform.risk_management.models import VaRReport


class VaREngine:
    """Calculates Parametric and Historical VaR ratios at configured confidence."""

    def __init__(self, confidence_level: float = 0.95) -> None:
        self.confidence_level = confidence_level

    def calculate_var(self, returns: np.ndarray, portfolio_value: float = 100000.0) -> VaRReport:
        """Compute parametric and historical VaR values.

        Formula:
            Parametric VaR = Portfolio Value * Z_score * Standard Deviation
            Historical VaR = Portfolio Value * Percentile of returns
        """
        if len(returns) < 2:
            return VaRReport(
                parametric_var=0.0,
                historical_var=0.0,
                confidence_level=self.confidence_level
            )

        # 1. Parametric VaR (using 1.645 for 95% confidence z-score)
        vol = np.std(returns)
        z_score = 1.645 if self.confidence_level == 0.95 else 2.33
        p_var = portfolio_value * z_score * vol

        # 2. Historical VaR
        pct = (1.0 - self.confidence_level) * 100.0
        h_var = -portfolio_value * np.percentile(returns, pct)

        return VaRReport(
            parametric_var=max(p_var, 0.0),
            historical_var=max(h_var, 0.0),
            confidence_level=self.confidence_level
        )
