"""ATR-based position sizing calculator."""

from __future__ import annotations

import logging
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from position_sizing.core.interfaces import ISizingCalculator

logger = logging.getLogger(__name__)


class ATRPositionCalculator(ISizingCalculator):
    """Calculates quantity using Average True Range (ATR) to determine the stop distance."""

    def calculate(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> tuple[float, list[str]]:
        """Calculate quantity.

        Kwargs:
            account_balance (float): Total account balance. Required; must be positive.
            risk_percent (float): Risk fraction. Default 0.01.
            risk_amount (float): Dollar risk amount (takes precedence if explicit).
            atr_multiplier (float): Multiplier for ATR to set stop distance. Default 2.0.
            atr (float): ATR value override. If not in context, must be supplied via this kwarg.
        """
        raw_balance = kwargs.get("account_balance", kwargs.get("balance"))
        if raw_balance is None or float(raw_balance) <= 0:
            logger.warning("ATRPosition: Missing or non-positive account balance.")
            return 0.0, ["Account balance must be provided and positive."]
        balance = float(raw_balance)
        risk_pct = float(kwargs.get("risk_percent", 0.01))
        atr_multiplier = float(kwargs.get("atr_multiplier", 2.0))
        # Retrieve ATR from TradingContext or explicit kwargs — NEVER use hidden fallback values
        atr = None
        if context.market_state and context.market_state.volume:
            if hasattr(context.market_state.volume, "atr") and context.market_state.volume.atr > 0:
                atr = float(context.market_state.volume.atr)

        if atr is None and "atr" in kwargs:
            raw_atr = float(kwargs["atr"])
            if raw_atr > 0:
                atr = raw_atr

        if atr is None or atr <= 0:
            logger.warning("ATRPosition: Missing or non-positive ATR parameter in context or kwargs.")
            return 0.0, ["Missing or invalid ATR parameter in context or kwargs."]

        stop_distance = atr * atr_multiplier

        if stop_distance <= 0:
            logger.warning("ATRPosition: Calculated stop distance must be positive. ATR=%s, Mult=%s", atr, atr_multiplier)
            return 0.0, ["Stop distance must be positive."]

        # Check if using fixed risk_amount or risk_percent
        explicit_risk_amount = kwargs.get("risk_amount")
        if explicit_risk_amount is not None:
            risk_amount = float(explicit_risk_amount)
        else:
            risk_amount = balance * risk_pct

        quantity = risk_amount / stop_distance
        reasons = [
            f"ATR Sizing: ATR={atr:.4f}, multiplier={atr_multiplier:.1f} resulting in "
            f"stop distance {stop_distance:.4f}. Risked ${risk_amount:.2f}."
        ]

        return quantity, reasons
