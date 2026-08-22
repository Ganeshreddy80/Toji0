"""Volatility adjusted position sizing calculator."""

from __future__ import annotations

import logging
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from position_sizing.core.interfaces import ISizingCalculator
from position_sizing.analysis.fixed_fractional import FixedFractionalCalculator

logger = logging.getLogger(__name__)


class VolatilityPositionCalculator(ISizingCalculator):
    """Adjusts position size based on current market volatility vs. historical average volatility."""

    def __init__(self, base_calculator: ISizingCalculator | None = None) -> None:
        self._base_calculator = base_calculator or FixedFractionalCalculator()

    def calculate(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> tuple[float, list[str]]:
        """Calculate quantity.

        Kwargs:
            historical_avg_atr (float): Average historical ATR. Defaults to current_atr if not provided.
            atr (float): Current ATR override. If not in context, must be supplied via this kwarg.
        """
        # 1. Run base calculator first
        base_qty, reasons = self._base_calculator.calculate(context, risk_assessment, **kwargs)
        if base_qty <= 0:
            return 0.0, reasons

        # 2. Retrieve current ATR — NEVER use hidden fallback values
        current_atr = None
        if context.market_state and context.market_state.volume:
            if hasattr(context.market_state.volume, "atr") and context.market_state.volume.atr > 0:
                current_atr = float(context.market_state.volume.atr)

        if current_atr is None and "atr" in kwargs:
            raw_atr = float(kwargs["atr"])
            if raw_atr > 0:
                current_atr = raw_atr

        if current_atr is None or current_atr <= 0:
            logger.warning("VolatilityPosition: Missing or non-positive ATR value in context or kwargs.")
            return 0.0, ["Missing or invalid ATR parameter in context or kwargs."]

        # 3. Retrieve average ATR
        avg_atr = float(kwargs.get("historical_avg_atr", current_atr))

        # Scale down size if current volatility is higher than historical average
        volatility_factor = 1.0
        if current_atr > avg_atr and avg_atr > 0:
            volatility_factor = avg_atr / current_atr

        adjusted_qty = base_qty * volatility_factor
        reasons.append(
            f"Volatility Adjuster: Current ATR={current_atr:.4f} vs Avg ATR={avg_atr:.4f}. "
            f"Applied scale factor {volatility_factor:.2f}. "
            f"Base Qty {base_qty:.4f} adjusted to {adjusted_qty:.4f}."
        )

        return adjusted_qty, reasons
