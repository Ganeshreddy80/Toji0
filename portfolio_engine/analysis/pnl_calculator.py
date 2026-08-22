from __future__ import annotations

from portfolio_engine.core.enums import PositionSide


class PnlCalculator:
    """Calculates realized and unrealized profit and loss (PnL) for trading positions."""

    @staticmethod
    def calculate_unrealized_pnl(
        side: PositionSide, quantity: float, average_entry: float, current_price: float
    ) -> float:
        """Compute unrealized profit/loss based on current price."""
        if quantity <= 0:
            return 0.0
        if side == PositionSide.LONG:
            return (current_price - average_entry) * quantity
        else:
            return (average_entry - current_price) * quantity

    @staticmethod
    def calculate_realized_pnl(
        side: PositionSide, average_entry: float, exit_price: float, quantity: float, fees: float = 0.0
    ) -> float:
        """Compute realized profit/loss on trade closure or reduction."""
        if quantity <= 0:
            return 0.0
        if side == PositionSide.LONG:
            return (exit_price - average_entry) * quantity - fees
        else:
            return (average_entry - exit_price) * quantity - fees

    @staticmethod
    def calculate_weighted_average_entry(
        current_qty: float, current_avg: float, fill_qty: float, fill_price: float
    ) -> float:
        """Calculate weighted entry cost when adding to a position."""
        total_qty = current_qty + fill_qty
        if total_qty <= 0:
            return 0.0
        return (current_qty * current_avg + fill_qty * fill_price) / total_qty
