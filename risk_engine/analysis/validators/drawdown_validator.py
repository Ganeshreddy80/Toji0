"""Drawdown Validator for the Risk Engine."""

from __future__ import annotations

from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.enums import RiskSeverity
from risk_engine.core.models import RiskFactor


class DrawdownValidator:
    """Checks maximum drawdown limits and permanent equity protection levels."""

    def validate(
        self, context: TradingContext, **kwargs: Any
    ) -> tuple[RiskFactor | None, float, str | None]:
        # 1. Resolve parameters from kwargs
        max_drawdown_pct = float(kwargs.get("max_drawdown_pct", 0.05))
        current_drawdown_pct = float(kwargs.get("current_drawdown_pct", 0.0))
        equity_protection_pct = float(kwargs.get("equity_protection_pct", 0.10))

        # 2. Evaluate conditions
        if current_drawdown_pct >= equity_protection_pct:
            return (
                RiskFactor(
                    id="RE_DD_001",
                    name="Equity Protection Level Breached",
                    severity=RiskSeverity.CRITICAL,
                    score=100.0,
                    description=f"Current drawdown of {current_drawdown_pct * 100:.2f}% "
                    f"exceeds absolute equity protection boundary of {equity_protection_pct * 100:.2f}%.",
                ),
                100.0,
                f"Equity protection breach: drawdown {current_drawdown_pct * 100:.2f}% >= {equity_protection_pct * 100:.2f}%.",
            )

        if current_drawdown_pct >= max_drawdown_pct:
            return (
                RiskFactor(
                    id="RE_DD_002",
                    name="Maximum Drawdown Exceeded",
                    severity=RiskSeverity.HIGH,
                    score=30.0,
                    description=f"Current drawdown of {current_drawdown_pct * 100:.2f}% "
                    f"exceeds limit of {max_drawdown_pct * 100:.2f}%.",
                ),
                30.0,
                f"Maximum drawdown exceeded: {current_drawdown_pct * 100:.2f}% >= {max_drawdown_pct * 100:.2f}%.",
            )

        # Warning threshold at 80% of max drawdown limit
        warning_level = max_drawdown_pct * 0.8
        if current_drawdown_pct >= warning_level:
            return (
                RiskFactor(
                    id="RE_DD_003",
                    name="Drawdown Warning Level Reached",
                    severity=RiskSeverity.MEDIUM,
                    score=10.0,
                    description=f"Current drawdown of {current_drawdown_pct * 100:.2f}% "
                    f"approaches maximum limit of {max_drawdown_pct * 100:.2f}%.",
                ),
                10.0,
                f"Drawdown warning: {current_drawdown_pct * 100:.2f}% >= {warning_level * 100:.2f}%.",
            )

        return None, 0.0, None
