"""Enums for the Confluence Engine."""

from __future__ import annotations

import enum


class SetupGrade(enum.Enum):
    """Setup quality grade based on confluence score."""

    A_PLUS = "A+"
    A = "A"
    B_PLUS = "B+"
    B = "B"
    C = "C"
    NO_TRADE = "No Trade"

    # Backward-compatible alias
    REJECT = "No Trade"


class RiskFlagType(enum.Enum):
    """Types of risk flags that can be raised by the Risk Flag Engine."""

    LOW_LIQUIDITY = "Low Liquidity"
    HIGH_VOLATILITY = "High Volatility"
    CORRELATION_RISK = "Correlation Risk"
    WEEKEND_RISK = "Weekend Risk"
    FUNDING_RISK = "Funding Risk"
    NEWS_EVENT_RISK = "News/Event Risk"
    SPREAD_RISK = "Spread Risk"
