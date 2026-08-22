"""Enums for the Portfolio Construction Engine."""

from __future__ import annotations

import enum


class PortfolioDecision(enum.Enum):
    """Execution posture decision for portfolio allocation."""

    REBALANCE = "REBALANCE"
    HOLD = "HOLD"
    DELEVERAGE = "DELEVERAGE"


class ConstraintType(enum.Enum):
    """Supported portfolio constraint types."""

    MAX_CORRELATION = "MAX_CORRELATION"
    MAX_WEIGHT_PER_ASSET = "MAX_WEIGHT_PER_ASSET"
    MIN_WEIGHT_PER_ASSET = "MIN_WEIGHT_PER_ASSET"
    MAX_POSITIONS = "MAX_POSITIONS"
    SECTOR_LIMIT = "SECTOR_LIMIT"
    MIN_PORTFOLIO_CONFIDENCE = "MIN_PORTFOLIO_CONFIDENCE"


class OptimizationObjective(enum.Enum):
    """Supported portfolio optimization objectives."""

    EQUAL_WEIGHT = "EQUAL_WEIGHT"
    CONFIDENCE_WEIGHTED = "CONFIDENCE_WEIGHTED"
    RISK_PARITY = "RISK_PARITY"
    MEAN_VARIANCE = "MEAN_VARIANCE"
