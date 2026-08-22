"""Portfolio Risk calculator checking gross/net exposures.
"""

from __future__ import annotations

from typing import Dict

from research_platform.risk_management.models import PortfolioRisk


class PortfolioRiskEvaluator:
    """Calculates aggregate metrics, net exposures, and beta mappings."""

    def __init__(self, default_beta: float = 1.0) -> None:
        self.default_beta = default_beta

    def calculate_portfolio_risk(
        self,
        positions_weights: Dict[str, float]
    ) -> PortfolioRisk:
        """Calculate net/gross parameters based on weights allocation."""
        longs = sum(w for w in positions_weights.values() if w > 0.0)
        shorts = sum(w for w in positions_weights.values() if w < 0.0)

        gross = longs + abs(shorts)
        net = longs + shorts

        return PortfolioRisk(
            gross_exposure=gross,
            net_exposure=net,
            beta=self.default_beta,
            diversification_score=0.85
        )
