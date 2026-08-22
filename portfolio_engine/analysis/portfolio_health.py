from __future__ import annotations

from portfolio_engine.core.models import PortfolioHealth


class PortfolioHealthCalculator:
    """Evaluates portfolio drawdown, leverage ratios, and risk bounds."""

    @staticmethod
    def calculate_health(
        portfolio_value: float,
        peak_value: float,
        gross_exposure: float,
        margin_used: float,
    ) -> PortfolioHealth:
        """Compute drawdown, leverage ratios and compile a PortfolioHealth model."""
        # 1. Drawdown calculation
        drawdown = 0.0
        if peak_value > 0.0 and portfolio_value < peak_value:
            drawdown = (peak_value - portfolio_value) / peak_value

        # 2. Leverage ratio
        leverage = 0.0
        if portfolio_value > 0.0:
            leverage = gross_exposure / portfolio_value

        # 3. Status determination
        status = "HEALTHY"
        if drawdown > 0.15 or leverage > 10.0:
            status = "CRITICAL"
        elif drawdown > 0.08 or leverage > 5.0:
            status = "WARNING"

        # 4. Risk exposure ratio
        risk_exposure = 0.0
        if portfolio_value > 0.0:
            risk_exposure = margin_used / portfolio_value

        return PortfolioHealth(
            status=status,
            drawdown=drawdown,
            leverage_ratio=leverage,
            risk_exposure_ratio=risk_exposure,
        )
