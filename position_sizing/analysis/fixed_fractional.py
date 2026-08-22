"""Fixed Fractional position sizing calculator."""

from __future__ import annotations

import logging
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from position_sizing.core.interfaces import ISizingCalculator

logger = logging.getLogger(__name__)


class FixedFractionalCalculator(ISizingCalculator):
    """Calculates quantity based on a fixed percentage of the account balance to risk."""

    def calculate(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> tuple[float, list[str]]:
        """Calculate quantity.

        Kwargs:
            account_balance (float): Total account balance. Required; must be positive.
            risk_percent (float): Risk fraction (e.g. 0.01 for 1%). Default 0.01.
            entry_price (float): Entry price level. Default 100.0.
            stop_distance (float): Price distance to stop-loss. If not provided, computed from stop_loss.
            stop_loss (float): Stop-loss price.
        """
        raw_balance = kwargs.get("account_balance", kwargs.get("balance"))
        if raw_balance is None or float(raw_balance) <= 0:
            logger.warning("FixedFractional: Missing or non-positive account balance.")
            return 0.0, ["Account balance must be provided and positive."]
        balance = float(raw_balance)
        risk_pct = float(kwargs.get("risk_percent", 0.01))
        entry_price = float(kwargs.get("entry_price", 100.0))

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
            logger.warning("FixedFractional: Missing or invalid stop distance.")
            return 0.0, ["Stop distance must be positive."]

        risk_amount = balance * risk_pct
        quantity = risk_amount / stop_distance
        reasons = [
            f"Fixed Fractional: Risked {risk_pct*100:.2f}% of {balance:.2f} balance (${risk_amount:.2f} risk) "
            f"with stop distance {stop_distance:.4f}."
        ]

        return quantity, reasons
