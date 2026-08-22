"""Portfolio Balanced position sizing calculator."""

from __future__ import annotations

import logging
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from position_sizing.core.interfaces import ISizingCalculator

logger = logging.getLogger(__name__)


class PortfolioBalancedCalculator(ISizingCalculator):
    """Calculates quantity by dividing total account capital equally across maximum open positions count."""

    def calculate(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> tuple[float, list[str]]:
        raw_balance = kwargs.get("balance", kwargs.get("account_balance"))
        if raw_balance is None or float(raw_balance) <= 0:
            logger.warning("PortfolioBalanced: Missing or non-positive account balance.")
            return 0.0, ["Account balance must be provided and positive."]
        balance = float(raw_balance)
        max_open = int(kwargs.get("max_open_positions", 10))
        entry_price = float(kwargs.get("entry_price", 100.0))

        if entry_price <= 0 or max_open <= 0:
            return 0.0, ["Invalid entry price or max open positions count."]

        allocation = balance / max_open
        quantity = allocation / entry_price
        return quantity, [f"Portfolio Balanced: divided balance equally across {max_open} target slots."]
