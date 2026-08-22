"""Fractional Kelly position sizing calculator."""

from __future__ import annotations

import logging
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from position_sizing.core.interfaces import ISizingCalculator

logger = logging.getLogger(__name__)


class FractionalKellyCalculator(ISizingCalculator):
    """Calculates quantity based on Kelly criterion scaled by a fractional factor (e.g. half/quarter Kelly)."""

    def calculate(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> tuple[float, list[str]]:
        win_rate = float(kwargs.get("win_rate", 0.55))
        rr_ratio = float(kwargs.get("rr_ratio", 2.0))
        fraction = float(kwargs.get("kelly_fraction", 0.5))
        raw_balance = kwargs.get("balance", kwargs.get("account_balance"))
        if raw_balance is None or float(raw_balance) <= 0:
            logger.warning("FractionalKelly: Missing or non-positive account balance.")
            return 0.0, ["Account balance must be provided and positive."]
        balance = float(raw_balance)
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

        if stop_distance is None or stop_distance <= 0 or rr_ratio <= 0:
            logger.warning("FractionalKelly: Missing or invalid stop distance or risk-to-reward ratio.")
            return 0.0, ["Invalid or missing stop-loss distance or risk-to-reward ratio for Kelly sizing."]

        # kelly formula: f = w - (1 - w) / R
        f = win_rate - (1.0 - win_rate) / rr_ratio
        f_scaled = max(0.0, f * fraction)

        quantity = (balance * f_scaled) / stop_distance
        reasons = [
            f"Fractional Kelly: win_rate={win_rate:.2f}, rr={rr_ratio:.2f}, fraction={fraction:.2f}, scaled Kelly %={f_scaled*100:.2f}%."
        ]

        return quantity, reasons
