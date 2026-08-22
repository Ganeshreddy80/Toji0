"""Risk budgeting and Marginal Contribution to Risk (MCTR) engine implementing IRiskBudgeter.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List
from research_platform.portfolio_optimizer.interfaces import IRiskBudgeter
from research_platform.portfolio_optimizer.models import RiskBudget

logger = logging.getLogger(__name__)


class RiskBudgeter(IRiskBudgeter):
    """Calculates risk contributions and evaluates budget limit compliance checks."""

    def evaluate_risk_budget(
        self,
        weights: Dict[str, float],
        covariance: List[List[float]],
        limits: Dict[str, float]
    ) -> RiskBudget:
        """Evaluate marginal risk contributions (MCTR) and risk contributions."""
        symbols = sorted(list(weights.keys()))
        n = len(symbols)

        # Map symbol to index
        sym_idx = {s: i for i, s in enumerate(symbols)}

        # Convert weights to vector aligned with index
        w_vec = [weights[s] for s in symbols]

        # Calculate Σ * w
        sigma_w = [0.0] * n
        for i in range(n):
            for j in range(n):
                sigma_w[i] += covariance[i][j] * w_vec[j]

        # Portfolio Volatility = sqrt(w^T * Σ * w)
        var_p = sum(w_vec[i] * sigma_w[i] for i in range(n))
        vol_p = math.sqrt(var_p) if var_p > 0 else 0.0

        marginal_contributions = {}
        for i, s in enumerate(symbols):
            # MCTR_i = (Σ * w)_i / vol_p
            mctr = sigma_w[i] / vol_p if vol_p > 0 else 0.0
            # Risk Contribution = w_i * MCTR_i
            rc = w_vec[i] * mctr
            marginal_contributions[s] = rc

        # Check budget breaches
        for s, limit in limits.items():
            rc = marginal_contributions.get(s, 0.0)
            if rc > limit:
                logger.warning("Risk budget breach detected for '%s': Contribution %.4f exceeds limit %.4f", s, rc, limit)

        return RiskBudget(
            limits=limits,
            marginal_contributions=marginal_contributions
        )
