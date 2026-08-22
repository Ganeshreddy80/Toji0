"""Sizing Selector for retrieving the appropriate position sizing calculator."""

from __future__ import annotations

import logging
from typing import Any

from position_sizing.core.enums import PositionSizingMethod
from position_sizing.core.interfaces import ISizingCalculator
from position_sizing.analysis.fixed_fractional import FixedFractionalCalculator
from position_sizing.analysis.fixed_risk import FixedRiskCalculator
from position_sizing.analysis.atr_position import ATRPositionCalculator
from position_sizing.analysis.volatility_position import VolatilityPositionCalculator
from position_sizing.analysis.kelly_position import KellyPositionCalculator
from position_sizing.analysis.fixed_size import FixedSizeCalculator
from position_sizing.analysis.fractional_kelly import FractionalKellyCalculator
from position_sizing.analysis.risk_budget_position import RiskBudgetPositionCalculator
from position_sizing.analysis.max_allocation import MaxAllocationCalculator
from position_sizing.analysis.min_allocation import MinAllocationCalculator
from position_sizing.analysis.portfolio_balanced import PortfolioBalancedCalculator

logger = logging.getLogger(__name__)


class SizingSelector:
    """Selects and constructs position sizing calculators."""

    def __init__(self) -> None:
        self._calculators: dict[PositionSizingMethod, ISizingCalculator] = {
            # Legacy mapping
            PositionSizingMethod.FIXED_FRACTIONAL: FixedFractionalCalculator(),
            PositionSizingMethod.FIXED_RISK: FixedRiskCalculator(),
            PositionSizingMethod.ATR: ATRPositionCalculator(),
            PositionSizingMethod.VOLATILITY: VolatilityPositionCalculator(),
            PositionSizingMethod.KELLY: KellyPositionCalculator(),

            # Sprint 7 Institutional Sizing Models
            PositionSizingMethod.PERCENTAGE_RISK: FixedFractionalCalculator(),
            PositionSizingMethod.FIXED_DOLLAR_RISK: FixedRiskCalculator(),
            PositionSizingMethod.ATR_SIZE: ATRPositionCalculator(),
            PositionSizingMethod.VOLATILITY_SIZE: VolatilityPositionCalculator(),
            PositionSizingMethod.KELLY_CRITERION: KellyPositionCalculator(),
            PositionSizingMethod.FIXED_SIZE: FixedSizeCalculator(),
            PositionSizingMethod.FRACTIONAL_KELLY: FractionalKellyCalculator(),
            PositionSizingMethod.RISK_BUDGET_SIZE: RiskBudgetPositionCalculator(),
            PositionSizingMethod.MAX_ALLOCATION: MaxAllocationCalculator(),
            PositionSizingMethod.MIN_ALLOCATION: MinAllocationCalculator(),
            PositionSizingMethod.PORTFOLIO_BALANCED: PortfolioBalancedCalculator(),
        }

    def select_calculator(
        self,
        method: PositionSizingMethod | str,
        **kwargs: Any,
    ) -> ISizingCalculator:
        """Resolve and return the appropriate calculator."""
        if isinstance(method, str):
            try:
                method_enum = PositionSizingMethod[method.upper()]
            except KeyError:
                raise ValueError(
                    f"SizingSelector: Unknown sizing method '{method}'. "
                    f"Valid methods are: {[m.name for m in PositionSizingMethod]}."
                )
        else:
            method_enum = method

        return self._calculators.get(method_enum, self._calculators[PositionSizingMethod.FIXED_FRACTIONAL])
