"""Position Sizing engine.
"""

from __future__ import annotations

import math
from typing import Any, Dict


class PositionSizer:
    """Calculates capital allocations using Kelly, Fixed Fractional, or Target Volatility formulas."""

    @staticmethod
    def calculate_size(
        sizing_type: str,
        params: Dict[str, Any],
        capital: float,
        price: float,
        volatility: float = 0.02
    ) -> float:
        """Calculate number of units to allocate.

        Args:
            sizing_type: FixedSize, FixedFractional, VolatilityTarget, Kelly.
            params: Parameters dictionary.
            capital: Available portfolio capital.
            price: Current asset price.
            volatility: Current asset rolling volatility percentage.

        Returns:
            Number of shares/contracts to trade.
        """
        if price <= 0.0 or capital <= 0.0:
            return 0.0

        if sizing_type == "FixedSize":
            # Simple unit count
            return float(params.get("units", 10.0))

        elif sizing_type == "FixedFractional":
            fraction = params.get("fraction", 0.02)  # risk 2% of capital
            stop_pct = params.get("stop_pct", 0.02)
            risk_amt = capital * fraction
            risk_per_share = price * stop_pct
            return float(risk_amt / (risk_per_share + 1e-10))

        elif sizing_type == "VolatilityTarget":
            target_vol = params.get("target_vol", 0.01)  # 1% daily vol target
            allocated_capital = capital * (target_vol / (volatility + 1e-10))
            return float(allocated_capital / price)

        elif sizing_type == "Kelly":
            fraction = params.get("kelly_fraction", 0.5)  # half Kelly
            win_prob = params.get("win_probability", 0.55)
            win_loss_ratio = params.get("win_loss_ratio", 1.2)  # b parameter
            
            # Kelly formula: f* = (p * b - q) / b
            q = 1.0 - win_prob
            kelly_f = (win_prob * win_loss_ratio - q) / (win_loss_ratio + 1e-10)
            kelly_f = max(kelly_f, 0.0)  # no shorting/negative allocation
            
            allocated_capital = capital * kelly_f * fraction
            return float(allocated_capital / price)

        return 1.0
