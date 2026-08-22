"""Fixed Risk position sizing calculator."""

from __future__ import annotations

import logging
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from position_sizing.core.interfaces import ISizingCalculator

logger = logging.getLogger(__name__)


class FixedRiskCalculator(ISizingCalculator):
    """Calculates quantity based on a fixed maximum dollar amount to risk."""

    def calculate(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> tuple[float, list[str]]:
        """Calculate quantity.

        Kwargs:
            risk_amount (float): Dollar amount to risk. Default 100.0.
            entry_price (float): Entry price level. Default 100.0.
            stop_distance (float): Price distance to stop-loss. If not provided, computed from stop_loss.
            stop_loss (float): Stop-loss price.
        """
        # Determine fixed dollar risk
        risk_amount = float(kwargs.get("risk_amount", 100.0))
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
            logger.warning("FixedRisk: Missing or invalid stop distance.")
            return 0.0, ["Missing or invalid stop-loss parameter (stop_loss or stop_distance must be positive)."]

        quantity = risk_amount / stop_distance
        reasons = [
            f"Fixed Risk: Risked fixed ${risk_amount:.2f} with stop distance {stop_distance:.4f}."
        ]

        return quantity, reasons
