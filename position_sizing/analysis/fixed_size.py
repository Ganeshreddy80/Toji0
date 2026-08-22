"""Fixed Size position sizing calculator."""

from __future__ import annotations

import logging
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from position_sizing.core.interfaces import ISizingCalculator

logger = logging.getLogger(__name__)


class FixedSizeCalculator(ISizingCalculator):
    """Calculates quantity based on a fixed quantity configuration."""

    def calculate(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> tuple[float, list[str]]:
        fixed_qty = float(kwargs.get("fixed_qty", 1.0))
        return fixed_qty, [f"Fixed Size: allocated fixed quantity of {fixed_qty} units."]
