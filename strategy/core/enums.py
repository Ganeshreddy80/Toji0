"""Enums for the Strategy Engine."""

from __future__ import annotations

import enum


class StrategyDecision(enum.Enum):
    """Trading setup decision representing execution posture."""

    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


class StrategyType(enum.Enum):
    """Supported strategy categories."""

    TREND_FOLLOWING = "Trend Following"
    BREAKOUT = "Breakout"
    REVERSAL = "Reversal"
    CONTINUATION = "Continuation"
    RANGE = "Range"
    MEAN_REVERSION = "Mean Reversion"
    MOMENTUM = "Momentum"


class SignalLifecycleState(enum.Enum):
    """
    Standardized lifecycle states for trade setup signals.
    Note: CANCELLED is reserved for future explicit signal cancellation workflows.
    """

    NEW = "NEW"
    ACTIVE = "ACTIVE"
    UPDATED = "UPDATED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"  # Reserved for future explicit cancellation workflow
