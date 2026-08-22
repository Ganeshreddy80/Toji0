"""Session Validator for the Risk Engine."""

from __future__ import annotations

from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.enums import RiskSeverity
from risk_engine.core.models import RiskFactor


class SessionValidator:
    """Checks active trading sessions, market close windows, and low-liquidity periods."""

    def validate(
        self, context: TradingContext, **kwargs: Any
    ) -> tuple[RiskFactor | None, float, str | None]:
        market_state = context.market_state

        # 1. Resolve limits and current states from kwargs
        market_closed = bool(kwargs.get("market_closed", False))
        low_liquidity_period = bool(kwargs.get("low_liquidity_period", False))

        # 2. Evaluate conditions
        if market_closed:
            return (
                RiskFactor(
                    id="RE_SESS_001",
                    name="Market Closed",
                    severity=RiskSeverity.CRITICAL,
                    score=100.0,
                    description="Trading proposal received outside market trading hours.",
                ),
                100.0,
                "Market is currently closed.",
            )

        if low_liquidity_period:
            return (
                RiskFactor(
                    id="RE_SESS_002",
                    name="Low Liquidity Session Period",
                    severity=RiskSeverity.MEDIUM,
                    score=15.0,
                    description="Trading proposal received during low liquidity session gaps.",
                ),
                15.0,
                "Low liquidity session period active.",
            )

        # 3. Inspect market state session
        if market_state and not market_state.session:
            return (
                RiskFactor(
                    id="RE_SESS_003",
                    name="Inactive Session State",
                    severity=RiskSeverity.MEDIUM,
                    score=15.0,
                    description="Market intelligence reports no active trading session.",
                ),
                15.0,
                "No active session identified by Market Intelligence.",
            )

        return None, 0.0, None
