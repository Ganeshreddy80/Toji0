"""Enums for the Market Intelligence Layer."""

from __future__ import annotations

import enum


class TrendDirection(enum.Enum):
    """Directional classification of trend."""

    UP = "UP"
    DOWN = "DOWN"
    SIDEWAYS = "SIDEWAYS"


class StructureBias(enum.Enum):
    """Structural bias of the market."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGING = "RANGING"


class SessionName(enum.Enum):
    """Timezone session identification."""

    ASIA = "ASIA"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    SYDNEY = "SYDNEY"
    TOKYO = "TOKYO"


class MarketPhase(enum.Enum):
    """Synthesized market phase."""

    ACCUMULATION = "ACCUMULATION"
    TRENDING = "TRENDING"
    DISTRIBUTION = "DISTRIBUTION"
    REVERSAL = "REVERSAL"


class ZoneType(enum.Enum):
    """Supply and Demand zone types."""

    SUPPLY = "SUPPLY"
    DEMAND = "DEMAND"


class SwingType(enum.Enum):
    """High and Low swing types."""

    HIGH = "HIGH"
    LOW = "LOW"


class VolumeExpansionState(enum.Enum):
    """Classification of volume expansion context."""

    NORMAL = "NORMAL"
    EXPANSION = "EXPANSION"
    CLIMATIC = "CLIMATIC"


class MarketRegime(enum.Enum):
    """Classification of market regime."""

    TRENDING = "TRENDING"
    RANGING = "RANGING"
    EXPANSION = "EXPANSION"
    CONTRACTION = "CONTRACTION"
    VOLATILE = "VOLATILE"
    ACCUMULATION = "ACCUMULATION"
    DISTRIBUTION = "DISTRIBUTION"


class HealthState(enum.Enum):
    """Health status for engine components."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class ReplayStatus(enum.Enum):
    """Status of a replay verification run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"

