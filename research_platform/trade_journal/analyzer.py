"""Trade analyzer calculating holding times, slippages, commissions, and excursions.
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TradeAnalyzer:
    """Computes transaction details and peak profit/loss excursions."""

    def calculate_slippage(self, target_price: float, filled_price: float, quantity: float) -> float:
        if target_price <= 0.0:
            return 0.0
        return abs(target_price - filled_price) * quantity

    def calculate_commission(self, price: float, quantity: float, fee_rate: float = 0.0005) -> float:
        return price * quantity * fee_rate

    def calculate_holding_time(self, entry_time: datetime, exit_time: datetime) -> float:
        return (exit_time - entry_time).total_seconds()

    def estimate_excursions(self, entry_price: float, exit_price: float, quantity: float, side: str, pnl: float) -> tuple[float, float]:
        """Estimate Maximum Favorable Excursion (MFE) and Maximum Adverse Excursion (MAE)."""
        # For simulation, MFE is the peak favorable excursion
        # If trade was profitable, peak favorable excursion reached slightly higher than exit
        if pnl > 0.0:
            mfe = pnl * 1.15
            mae = pnl * 0.15
        else:
            mfe = abs(pnl) * 0.10
            mae = abs(pnl) * 1.20
            
        return mfe, mae
