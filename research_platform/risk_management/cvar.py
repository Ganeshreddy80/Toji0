"""Conditional Value-at-Risk Engine calculating Expected Shortfall.
"""

from __future__ import annotations

import numpy as np
from datetime import datetime, timezone

from research_platform.risk_management.models import CVaRReport


class CVaREngine:
    """Calculates Expected Shortfall below VaR limits."""

    def __init__(self, confidence_level: float = 0.95) -> None:
        self.confidence_level = confidence_level

    def calculate_cvar(self, returns: np.ndarray, portfolio_value: float = 100000.0) -> CVaRReport:
        """Compute Expected Shortfall average returns.

        Formula:
            CVaR = Average of returns that fall below the VaR threshold
        """
        if len(returns) < 2:
            return CVaRReport(
                expected_shortfall=0.0,
                confidence_level=self.confidence_level
            )

        pct = (1.0 - self.confidence_level) * 100.0
        var_threshold = np.percentile(returns, pct)
        
        tail_returns = returns[returns <= var_threshold]
        
        if len(tail_returns) > 0:
            avg_tail = np.mean(tail_returns)
            es = -portfolio_value * avg_tail
        else:
            es = 0.0

        return CVaRReport(
            expected_shortfall=max(es, 0.0),
            confidence_level=self.confidence_level
        )
