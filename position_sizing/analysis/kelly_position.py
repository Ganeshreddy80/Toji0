"""Kelly Criterion position sizing calculator."""

from __future__ import annotations

import logging
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from position_sizing.core.interfaces import ISizingCalculator
from position_sizing.core.enums import KellyFraction

logger = logging.getLogger(__name__)


class KellyPositionCalculator(ISizingCalculator):
    """Calculates position size using the Kelly Criterion based on strategy performance."""

    def calculate(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> tuple[float, list[str]]:
        """Calculate quantity.

        Kwargs:
            win_rate (float): Winning probability (0.0 to 1.0). Default 0.50.
            payoff_ratio (float): Average win / average loss ratio. Default 2.0.
            kelly_fraction (str or KellyFraction): Choose FULL, HALF, or QUARTER. Default HALF.
            account_balance (float): Total account balance. Required; must be positive.
            entry_price (float): Entry price. Default 100.
            stop_distance (float): Price distance to stop-loss.
            stop_loss (float): Stop-loss price.
        """
        win_rate = float(kwargs.get("win_rate", 0.50))
        payoff_ratio = float(kwargs.get("payoff_ratio", 2.0))
        fraction_param = kwargs.get("kelly_fraction", KellyFraction.HALF)
        raw_balance = kwargs.get("account_balance", kwargs.get("balance"))
        if raw_balance is None or float(raw_balance) <= 0:
            logger.warning("Kelly: Missing or non-positive account balance.")
            return 0.0, ["Account balance must be provided and positive."]
        balance = float(raw_balance)
        entry_price = float(kwargs.get("entry_price", 100.0))

        if win_rate <= 0 or win_rate >= 1:
            logger.warning("Kelly: Win rate must be between 0 and 1. Received %s", win_rate)
            return 0.0, ["Win rate must be between 0 and 1 exclusive."]

        if payoff_ratio <= 0:
            logger.warning("Kelly: Payoff ratio must be positive. Received %s", payoff_ratio)
            return 0.0, ["Payoff ratio must be positive."]

        # Calculate Kelly percentage: K% = W - (1 - W) / R
        kelly_pct = win_rate - (1.0 - win_rate) / payoff_ratio

        if kelly_pct <= 0:
            reasons = [f"Kelly: Negative Kelly score calculated ({kelly_pct:.4f}). Sizing is restricted to 0."]
            return 0.0, reasons

        # Apply fraction multiplier
        fraction_multiplier = 0.5
        fraction_str = "HALF"
        if isinstance(fraction_param, str):
            fraction_name = fraction_param.upper()
        else:
            fraction_name = fraction_param.name

        if fraction_name == "FULL":
            fraction_multiplier = 1.0
            fraction_str = "FULL"
        elif fraction_name == "QUARTER":
            fraction_multiplier = 0.25
            fraction_str = "QUARTER"
        else:
            fraction_multiplier = 0.5
            fraction_str = "HALF"

        effective_risk_pct = kelly_pct * fraction_multiplier
        risk_amount = balance * effective_risk_pct

        # Determine stop distance — NEVER fabricate fallback values
        stop_distance = kwargs.get("stop_distance")
        if stop_distance is not None:
            stop_distance = float(stop_distance)
        else:
            stop_loss = kwargs.get("stop_loss")
            if stop_loss is not None and float(stop_loss) > 0 and float(stop_loss) != entry_price:
                stop_distance = abs(entry_price - float(stop_loss))
            else:
                stop_distance = None

        if stop_distance is None or stop_distance <= 0:
            logger.warning("Kelly: Missing or invalid stop distance. Received %s", stop_distance)
            return 0.0, ["Missing or invalid stop-loss parameter (stop_loss or stop_distance must be positive)."]

        quantity = risk_amount / stop_distance
        reasons = [
            f"Kelly ({fraction_str}): WinRate={win_rate*100:.1f}%, PayoffRatio={payoff_ratio:.2f}. "
            f"Kelly%={kelly_pct*100:.2f}%, EffectiveRisk%={effective_risk_pct*100:.2f}%. "
            f"Risked ${risk_amount:.2f} with stop distance {stop_distance:.4f}."
        ]

        return quantity, reasons
