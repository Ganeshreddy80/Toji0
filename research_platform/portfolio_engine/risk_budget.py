"""Risk Budgeting engine calculating VaR, CVaR, and component risk contributions.
"""

from __future__ import annotations

import math
import numpy as np
from typing import Dict

from research_platform.portfolio_engine.interfaces import IRiskBudget
from research_platform.portfolio_engine.models import CovarianceMatrix, PortfolioWeights, RiskContribution


class PortfolioRiskBudget(IRiskBudget):
    """Calculates VaR, CVaR, expected shortfall, marginal and component risk contributions."""

    def __init__(self, confidence_level: float = 0.95) -> None:
        self.confidence_level = confidence_level

    def calculate_risk_contributions(self, weights: PortfolioWeights, cov: CovarianceMatrix) -> RiskContribution:
        """Calculate marginal and component risk contributions across assets.

        Formula:
            MCTR = (Cov @ w) / sqrt(w.T @ Cov @ w)
            CCTR = w * MCTR
            %CTR = CCTR / total_risk
        """
        symbols = cov.symbols
        n = len(symbols)
        
        # Build weight array aligned to covariance symbols order
        w_arr = np.array([weights.weights.get(sym, 0.0) for sym in symbols])
        cov_mat = np.array(cov.matrix)

        # 1. Portfolio Volatility
        port_variance = w_arr.T @ cov_mat @ w_arr
        port_vol = np.sqrt(port_variance) if port_variance > 0 else 1e-10

        # 2. Marginal Contribution to Total Risk (MCTR)
        mctr = (cov_mat @ w_arr) / port_vol

        # 3. Component Contribution to Total Risk (CCTR)
        cctr = w_arr * mctr

        # 4. Percentage Contribution (%CTR)
        pct_ctr = cctr / port_vol

        marginal_dict = {symbols[i]: float(mctr[i]) for i in range(n)}
        component_dict = {symbols[i]: float(cctr[i]) for i in range(n)}
        pct_dict = {symbols[i]: float(pct_ctr[i]) for i in range(n)}

        return RiskContribution(
            marginal_contribution=marginal_dict,
            component_contribution=component_dict,
            percentage_contribution=pct_dict
        )

    @staticmethod
    def calculate_var_cvar(
        weights: PortfolioWeights,
        cov: CovarianceMatrix,
        confidence: float = 0.95
    ) -> tuple[float, float]:
        """Estimate parametric Value-at-Risk (VaR) and Conditional VaR (CVaR)."""
        symbols = cov.symbols
        w_arr = np.array([weights.weights.get(sym, 0.0) for sym in symbols])
        cov_mat = np.array(cov.matrix)

        port_variance = w_arr.T @ cov_mat @ w_arr
        port_vol = math.sqrt(port_variance) if port_variance > 0 else 0.0

        # Parametric VaR (assuming 95% confidence level, z = 1.645)
        # We assume daily returns mean is 0.0 for conservative bounds
        z_score = 1.645 if confidence == 0.95 else 2.33
        var_val = port_vol * z_score

        # Parametric CVaR = mean - vol * (phi(z) / (1 - alpha))
        # For z_score = 1.645 (95%): phi(1.645) = exp(-1.645^2 / 2) / sqrt(2*pi) = 0.103
        # phi(z) / 0.05 = 0.103 / 0.05 = 2.06
        phi_z = math.exp(-0.5 * (z_score ** 2)) / math.sqrt(2.0 * math.pi)
        cvar_val = port_vol * (phi_z / (1.0 - confidence))

        return var_val, cvar_val
