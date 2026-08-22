from __future__ import annotations

from typing import List
from portfolio_engine.core.enums import PositionSide
from portfolio_engine.core.models import Position


class ExposureCalculator:
    """Computes gross and net portfolio market exposure metrics."""

    @staticmethod
    def calculate_exposures(positions: List[Position]) -> tuple[float, float]:
        """Calculate gross and net exposure from a list of positions.

        Returns:
            tuple[float, float]: (gross_exposure, net_exposure)
        """
        gross = 0.0
        net = 0.0

        for pos in positions:
            # Market value is positive quantity * price
            mval = pos.quantity * pos.current_price
            gross += mval
            if pos.side == PositionSide.LONG:
                net += mval
            else:
                net -= mval

        return gross, net
