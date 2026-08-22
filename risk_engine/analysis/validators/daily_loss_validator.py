"""Daily Loss Validator for the Risk Engine."""

from __future__ import annotations

from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.enums import RiskSeverity
from risk_engine.core.models import RiskFactor


class DailyLossValidator:
    """Checks daily loss limits, maximum trade counts, and daily stop-out flags."""

    def validate(
        self, context: TradingContext, **kwargs: Any
    ) -> tuple[RiskFactor | None, float, str | None]:
        # 1. Resolve limits and current states from kwargs
        daily_loss_limit_pct = float(kwargs.get("daily_loss_limit_pct", 0.02))
        current_daily_loss_pct = float(kwargs.get("current_daily_loss_pct", 0.0))
        max_daily_trades = int(kwargs.get("max_daily_trades", 10))
        current_daily_trades = int(kwargs.get("current_daily_trades", 0))
        daily_stop_reached = bool(kwargs.get("daily_stop_reached", False))

        # 2. Evaluate conditions
        if daily_stop_reached:
            return (
                RiskFactor(
                    id="RE_DL_001",
                    name="Daily Stop Out Reached",
                    severity=RiskSeverity.CRITICAL,
                    score=100.0,
                    description="Daily stop out has been reached or manually triggered.",
                ),
                100.0,
                "Daily stop out is active.",
            )

        if current_daily_loss_pct >= daily_loss_limit_pct:
            return (
                RiskFactor(
                    id="RE_DL_002",
                    name="Daily Loss Limit Exceeded",
                    severity=RiskSeverity.CRITICAL,
                    score=100.0,
                    description=f"Current daily loss of {current_daily_loss_pct * 100:.2f}% "
                    f"exceeds limit of {daily_loss_limit_pct * 100:.2f}%.",
                ),
                100.0,
                f"Daily loss limit exceeded: {current_daily_loss_pct * 100:.2f}% >= {daily_loss_limit_pct * 100:.2f}%.",
            )

        if current_daily_trades >= max_daily_trades:
            return (
                RiskFactor(
                    id="RE_DL_003",
                    name="Maximum Daily Trades Reached",
                    severity=RiskSeverity.HIGH,
                    score=25.0,
                    description=f"Current daily trades of {current_daily_trades} "
                    f"reaches or exceeds maximum allowed of {max_daily_trades}.",
                ),
                25.0,
                f"Maximum daily trades limit reached: {current_daily_trades} >= {max_daily_trades}.",
            )

        return None, 0.0, None
