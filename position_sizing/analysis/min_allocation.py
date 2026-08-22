"""Minimum Allocation position sizing calculator."""

from __future__ import annotations

import logging
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from position_sizing.core.interfaces import ISizingCalculator

logger = logging.getLogger(__name__)


class MinAllocationCalculator(ISizingCalculator):
    """Calculates quantity based on a minimum dollar capital allocation limit."""

    def calculate(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> tuple[float, list[str]]:
        min_alloc = float(kwargs.get("min_allocation", 1000.0))
        entry_price = float(kwargs.get("entry_price", 100.0))

        if entry_price <= 0:
            return 0.0, ["Invalid entry price."]

        quantity = min_alloc / entry_price
        return quantity, [f"Min Allocation: allocated min capital of ${min_alloc:.2f}."]
