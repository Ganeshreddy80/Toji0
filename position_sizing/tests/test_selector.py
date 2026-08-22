"""Unit tests for the position sizing selector."""

from __future__ import annotations

import pytest

from position_sizing.core.enums import PositionSizingMethod
from position_sizing.analysis.sizing_selector import SizingSelector
from position_sizing.analysis.fixed_fractional import FixedFractionalCalculator
from position_sizing.analysis.fixed_risk import FixedRiskCalculator
from position_sizing.analysis.atr_position import ATRPositionCalculator
from position_sizing.analysis.volatility_position import VolatilityPositionCalculator
from position_sizing.analysis.kelly_position import KellyPositionCalculator


def test_sizing_selector_select():
    """Verify selector maps methods to the correct calculator instance."""
    selector = SizingSelector()

    # Enum mapping
    assert isinstance(
        selector.select_calculator(PositionSizingMethod.FIXED_FRACTIONAL),
        FixedFractionalCalculator,
    )
    assert isinstance(
        selector.select_calculator(PositionSizingMethod.FIXED_RISK),
        FixedRiskCalculator,
    )
    assert isinstance(
        selector.select_calculator(PositionSizingMethod.ATR),
        ATRPositionCalculator,
    )
    assert isinstance(
        selector.select_calculator(PositionSizingMethod.VOLATILITY),
        VolatilityPositionCalculator,
    )
    assert isinstance(
        selector.select_calculator(PositionSizingMethod.KELLY),
        KellyPositionCalculator,
    )

    # String mapping
    assert isinstance(
        selector.select_calculator("fixed_risk"),
        FixedRiskCalculator,
    )
    assert isinstance(
        selector.select_calculator("atr"),
        ATRPositionCalculator,
    )


def test_sizing_selector_unknown_method_raises():
    """Task 2A: Unknown method string must raise ValueError, not silently fall back."""
    selector = SizingSelector()
    with pytest.raises(ValueError, match="Unknown sizing method"):
        selector.select_calculator("unknown_method")

