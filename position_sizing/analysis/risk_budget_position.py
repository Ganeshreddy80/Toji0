"""Risk Budget position sizing calculator."""

from __future__ import annotations

import logging
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from position_sizing.core.interfaces import ISizingCalculator

logger = logging.getLogger(__name__)


class RiskBudgetPositionCalculator(ISizingCalculator):
    """Calculates quantity based on remaining portfolio risk budget allocation."""

    def calculate(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> tuple[float, list[str]]:
        budget = float(kwargs.get("remaining_risk_budget", 5000.0))
        entry_price = float(kwargs.get("entry_price", 100.0))

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
            logger.warning("RiskBudget: Missing or invalid stop distance.")
            return 0.0, ["Missing or invalid stop-loss parameter (stop_loss or stop_distance must be positive)."]

        quantity = budget / stop_distance
        return quantity, [f"Risk Budget Size: allocated based on remaining budget ${budget:.2f}."]
