"""Maximum Allocation position sizing calculator."""

from __future__ import annotations

import logging
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from position_sizing.core.interfaces import ISizingCalculator

logger = logging.getLogger(__name__)


class MaxAllocationCalculator(ISizingCalculator):
    """Calculates quantity based on a maximum dollar capital allocation limit."""

    def calculate(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> tuple[float, list[str]]:
        max_alloc = float(kwargs.get("max_allocation", 50000.0))
        entry_price = float(kwargs.get("entry_price", 100.0))

        if entry_price <= 0:
            return 0.0, ["Invalid entry price."]

        quantity = max_alloc / entry_price
        return quantity, [f"Max Allocation: allocated max capital of ${max_alloc:.2f}."]
