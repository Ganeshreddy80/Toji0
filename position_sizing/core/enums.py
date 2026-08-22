"""Enums for the Position Sizing Engine subsystem."""

from enum import Enum


class PositionSizingMethod(str, Enum):
    """Supported position sizing algorithms."""

    # Legacy mappings (for backward compatibility)
    FIXED_FRACTIONAL = "FIXED_FRACTIONAL"
    FIXED_RISK = "FIXED_RISK"
    ATR = "ATR"
    VOLATILITY = "VOLATILITY"
    KELLY = "KELLY"

    # Sprint 7 Institutional Sizing Models
    FIXED_SIZE = "FIXED_SIZE"
    FIXED_DOLLAR_RISK = "FIXED_DOLLAR_RISK"
    PERCENTAGE_RISK = "PERCENTAGE_RISK"
    KELLY_CRITERION = "KELLY_CRITERION"
    FRACTIONAL_KELLY = "FRACTIONAL_KELLY"
    ATR_SIZE = "ATR_SIZE"
    VOLATILITY_SIZE = "VOLATILITY_SIZE"
    RISK_BUDGET_SIZE = "RISK_BUDGET_SIZE"
    MAX_ALLOCATION = "MAX_ALLOCATION"
    MIN_ALLOCATION = "MIN_ALLOCATION"
    PORTFOLIO_BALANCED = "PORTFOLIO_BALANCED"


class KellyFraction(str, Enum):
    """Kelly fraction scaling choices."""

    FULL = "FULL"
    HALF = "HALF"
    QUARTER = "QUARTER"


class SizingStatus(str, Enum):
    """Status indicating the result of the sizing calculation."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ADJUSTED = "ADJUSTED"
