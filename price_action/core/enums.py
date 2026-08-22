"""Enums for the Price Action Engine."""

from __future__ import annotations

import enum


class PatternType(enum.Enum):
    """Enumerate all price action patterns."""

    UNKNOWN = "UNKNOWN"
    TRIANGLE = "TRIANGLE"
    ASC_TRIANGLE = "ASC_TRIANGLE"
    DESC_TRIANGLE = "DESC_TRIANGLE"
    SYMMETRIC_TRIANGLE = "SYMMETRIC_TRIANGLE"
    WEDGE = "WEDGE"
    RISING_WEDGE = "RISING_WEDGE"
    FALLING_WEDGE = "FALLING_WEDGE"
    CHANNEL = "CHANNEL"
    ASC_CHANNEL = "ASC_CHANNEL"
    DESC_CHANNEL = "DESC_CHANNEL"
    FLAG = "FLAG"
    BULL_FLAG = "BULL_FLAG"
    BEAR_FLAG = "BEAR_FLAG"
    PENNANT = "PENNANT"
    RECTANGLE = "RECTANGLE"
    DOUBLE_TOP = "DOUBLE_TOP"
    DOUBLE_BOTTOM = "DOUBLE_BOTTOM"
    TRIPLE_TOP = "TRIPLE_TOP"
    TRIPLE_BOTTOM = "TRIPLE_BOTTOM"
    HEAD_AND_SHOULDERS = "HEAD_AND_SHOULDERS"
    INVERSE_HEAD_AND_SHOULDERS = "INVERSE_HEAD_AND_SHOULDERS"
    CUP_AND_HANDLE = "CUP_AND_HANDLE"
    ROUNDING_BOTTOM = "ROUNDING_BOTTOM"
    ROUNDED_BOTTOM = "ROUNDED_BOTTOM"
    ROUNDED_TOP = "ROUNDED_TOP"
    DIAMOND = "DIAMOND"
    DIAMOND_TOP = "DIAMOND_TOP"
    DIAMOND_BOTTOM = "DIAMOND_BOTTOM"
    BROADENING = "BROADENING"
    HARMONIC = "HARMONIC"
    WYCKOFF = "WYCKOFF"


class PatternDirection(enum.Enum):
    """Directional classification of a price action pattern."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class PatternStatus(enum.Enum):
    """Lifecycle status of a detected price action pattern."""

    DEVELOPING = "DEVELOPING"
    CONFIRMED = "CONFIRMED"
    INVALIDATED = "INVALIDATED"
    COMPLETED = "COMPLETED"


class SwingType(enum.Enum):
    """Classification of swing pivot points."""

    SWING_HIGH = "SWING_HIGH"
    SWING_LOW = "SWING_LOW"


class MarketStructureType(enum.Enum):
    """Market structure shift and continuation classifications."""

    BOS = "BOS"  # Break of Structure
    CHOCH = "CHOCH"  # Change of Character
    HH = "HH"  # Higher High
    HL = "HL"  # Higher Low
    LH = "LH"  # Lower High
    LL = "LL"  # Lower Low
    RANGE = "RANGE"


class TrendDirection(enum.Enum):
    """Trend direction classification."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    SIDEWAYS = "SIDEWAYS"


class LiquidityType(enum.Enum):
    """Liquidity pool classification."""

    BSL = "BSL"  # Buy-Side Liquidity (above swing highs)
    SSL = "SSL"  # Sell-Side Liquidity (below swing lows)


class ZoneType(enum.Enum):
    """Premium and Discount price zone classifications."""

    DEEP_DISCOUNT = "DEEP_DISCOUNT"  # < 25% of dealing range
    DISCOUNT = "DISCOUNT"            # 25% - 50% of dealing range
    EQUILIBRIUM = "EQUILIBRIUM"      # ~ 50% of dealing range
    PREMIUM = "PREMIUM"              # 50% - 75% of dealing range
    DEEP_PREMIUM = "DEEP_PREMIUM"    # > 75% of dealing range


class MarketRegimeType(enum.Enum):
    """Macro market regime classification."""

    TRENDING_BULLISH = "TRENDING_BULLISH"
    TRENDING_BEARISH = "TRENDING_BEARISH"
    RANGING = "RANGING"
    VOLATILE_EXPANSION = "VOLATILE_EXPANSION"
    COMPRESSING_CONSOLIDATION = "COMPRESSING_CONSOLIDATION"


class DivergenceType(enum.Enum):
    """Momentum divergence classification."""

    BULLISH_DIVERGENCE = "BULLISH_DIVERGENCE"
    BEARISH_DIVERGENCE = "BEARISH_DIVERGENCE"
    NONE = "NONE"

