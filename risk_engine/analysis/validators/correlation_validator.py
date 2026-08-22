"""Correlation Validator for the Risk Engine."""

from __future__ import annotations

from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.enums import RiskSeverity
from risk_engine.core.models import RiskFactor


class CorrelationValidator:
    """Checks portfolio asset correlation and blocks duplicate exposure or highly correlated assets."""

    def validate(
        self, context: TradingContext, **kwargs: Any
    ) -> tuple[RiskFactor | None, float, str | None]:
        symbol = context.symbol
        market_state = context.market_state

        # 1. Resolve parameters from kwargs
        max_correlation_limit = float(kwargs.get("max_correlation_limit", 0.7))
        portfolio_correlations = kwargs.get("portfolio_correlations", {})
        existing_portfolio_symbols = list(kwargs.get("existing_portfolio_symbols", []))

        # 2. Check for duplicate exposure
        if symbol in existing_portfolio_symbols:
            return (
                RiskFactor(
                    id="RE_CORR_001",
                    name="Duplicate Asset Exposure",
                    severity=RiskSeverity.HIGH,
                    score=25.0,
                    description=f"Asset {symbol} is already held in the portfolio.",
                ),
                25.0,
                f"Duplicate exposure check failed: {symbol} is already in portfolio.",
            )

        # 3. Check for high correlation with existing portfolio
        symbol_corr = float(portfolio_correlations.get(symbol, 0.0))
        if symbol_corr > max_correlation_limit:
            return (
                RiskFactor(
                    id="RE_CORR_002",
                    name="High Portfolio Correlation",
                    severity=RiskSeverity.HIGH,
                    score=20.0,
                    description=f"Asset {symbol} has a portfolio correlation of {symbol_corr:.2f} "
                    f"exceeding max limit of {max_correlation_limit:.2f}.",
                ),
                20.0,
                f"High portfolio correlation detected: {symbol_corr:.2f} > {max_correlation_limit:.2f}.",
            )

        # 4. Check for high correlation values inside market context
        if market_state and market_state.market_context and market_state.market_context.correlation:
            for correlated_symbol, correlation_val in market_state.market_context.correlation.items():
                if correlation_val > max_correlation_limit:
                    return (
                        RiskFactor(
                            id="RE_CORR_003",
                            name="High Systemic Correlation Exposure",
                            severity=RiskSeverity.MEDIUM,
                            score=15.0,
                            description=f"Asset {symbol} has a correlation of {correlation_val:.2f} "
                            f"with {correlated_symbol} exceeding max limit of {max_correlation_limit:.2f}.",
                        ),
                        15.0,
                        f"Systemic correlation spike: {symbol}-{correlated_symbol} is {correlation_val:.2f}.",
                    )

        return None, 0.0, None
