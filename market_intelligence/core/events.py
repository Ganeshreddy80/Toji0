"""System events for the Market Intelligence Layer.

All events are frozen dataclasses inheriting from BaseEvent.
"""

from __future__ import annotations

from dataclasses import dataclass

from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class MILInitialized(BaseEvent):
    """Fired when the Market Intelligence Layer plugin starts successfully."""


@dataclass(frozen=True)
class MILShutdown(BaseEvent):
    """Fired when the Market Intelligence Layer plugin shuts down."""


@dataclass(frozen=True)
class MarketStateUpdated(BaseEvent):
    """Fired when a symbol's timeframe-specific MarketState is updated.

    Payload should contain keys:
        symbol: str
        timeframe: str
        state: dict representing the serialized MarketState.
    """


@dataclass(frozen=True)
class MarketSnapshotCreated(BaseEvent):
    """Fired when a comprehensive MarketSnapshot is saved.

    Payload should contain keys:
        snapshot_id: str
        symbol: str
        timestamp: str (ISO)
        snapshot: dict representing the serialized MarketSnapshot.
    """


@dataclass(frozen=True)
class ContextUpdated(BaseEvent):
    """Fired when the synthesized MarketContext transitions phase or bias.

    Payload should contain keys:
        symbol: str
        old_phase: str
        new_phase: str
        dominant_bias: str
    """


@dataclass(frozen=True)
class ConfidenceUpdated(BaseEvent):
    """Fired when the Confidence score changes.

    Payload should contain keys:
        symbol: str
        old_score: float
        new_score: float
        reasons: list[str]
    """


@dataclass(frozen=True)
class StoryGenerated(BaseEvent):
    """Fired when a narrative Story is generated.

    Payload should contain keys:
        symbol: str
        narrative: str
        supporting_events: list[str]
    """


@dataclass(frozen=True)
class SwingHighConfirmed(BaseEvent):
    """Fired when a Swing High is confirmed at index t (detected at t+k)."""


@dataclass(frozen=True)
class SwingLowConfirmed(BaseEvent):
    """Fired when a Swing Low is confirmed at index t (detected at t+k)."""


@dataclass(frozen=True)
class StructureUpdated(BaseEvent):
    """Fired when a swing point is classified (HH, HL, LH, LL)."""


@dataclass(frozen=True)
class TrendChanged(BaseEvent):
    """Fired when Trend direction changes (UNKNOWN, BULLISH, BEARISH, RANGING)."""


@dataclass(frozen=True)
class BreakOfStructureDetected(BaseEvent):
    """Fired when a trend-following break of structure occurs on close."""


@dataclass(frozen=True)
class ChangeOfCharacterDetected(BaseEvent):
    """Fired when a counter-trend Change of Character occurs on close."""


@dataclass(frozen=True)
class LiquiditySwept(BaseEvent):
    """Fired when liquidity is swept on a swing point."""


@dataclass(frozen=True)
class SupplyZoneCreated(BaseEvent):
    """Fired when a new Supply Zone is created."""


@dataclass(frozen=True)
class DemandZoneCreated(BaseEvent):
    """Fired when a new Demand Zone is created."""


@dataclass(frozen=True)
class ZoneMitigated(BaseEvent):
    """Fired when a supply or demand zone is tested (mitigated) by price."""


@dataclass(frozen=True)
class ZoneInvalidated(BaseEvent):
    """Fired when a supply or demand zone is invalidated (broken) by price."""


@dataclass(frozen=True)
class SupportResistanceUpdated(BaseEvent):
    """Fired when support & resistance horizontal levels are clustered or updated."""


@dataclass(frozen=True)
class VolumeContextUpdated(BaseEvent):
    """Fired when volume analytics are updated for a symbol's timeframe."""


@dataclass(frozen=True)
class SessionChanged(BaseEvent):
    """Fired when the active session transitions."""


@dataclass(frozen=True)
class SessionUpdated(BaseEvent):
    """Fired when active session bounds update."""


@dataclass(frozen=True)
class SessionBreakout(BaseEvent):
    """Fired when a session range breakout occurs."""


@dataclass(frozen=True)
class TimeframeAlignmentUpdated(BaseEvent):
    """Fired when timeframe alignment metrics are calculated."""


@dataclass(frozen=True)
class MarketRegimeChanged(BaseEvent):
    """Fired when the classified market regime changes."""


@dataclass(frozen=True)
class CorrelationUpdated(BaseEvent):
    """Fired when rolling asset correlations are updated."""


@dataclass(frozen=True)
class MarketContextUpdated(BaseEvent):
    """Fired when the immutable MarketContext is generated."""


# ── Sprint 5 Events ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConfidenceScoreUpdated(BaseEvent):
    """Fired when confidence score is calculated.

    Payload should contain keys:
        symbol: str
        timeframe: str
        score: float
        contribution_breakdown: dict[str, float]
    """


@dataclass(frozen=True)
class MarketStoryGenerated(BaseEvent):
    """Fired when a structured narrative story is generated.

    Payload should contain keys:
        symbol: str
        timeframe: str
        sections: dict[str, str]
        supporting_events: list[str]
    """


@dataclass(frozen=True)
class ReplayCompleted(BaseEvent):
    """Fired when a replay verification run completes successfully.

    Payload should contain keys:
        symbol: str
        total_candles: int
        matched: bool
        duration_ms: float
    """


@dataclass(frozen=True)
class ReplayFailed(BaseEvent):
    """Fired when a replay verification run detects divergence.

    Payload should contain keys:
        symbol: str
        divergence_at: int
        hash_live: str
        hash_replay: str
    """


@dataclass(frozen=True)
class HealthReportGenerated(BaseEvent):
    """Fired when a health report is generated.

    Payload should contain keys:
        overall_status: str
        engine_statuses: dict[str, str]
        dependency_failures: list[str]
    """


# ─── Sprint 5 New Analytical Events ──────────────────────────────────────────

@dataclass(frozen=True)
class MarketRegimeDetected(BaseEvent):
    """Fired when a new Market Regime is calculated/detected."""


@dataclass(frozen=True)
class TrendAnalyzed(BaseEvent):
    """Fired when Trend calculations are processed."""


@dataclass(frozen=True)
class VolatilityUpdated(BaseEvent):
    """Fired when Volatility calculations are updated."""


@dataclass(frozen=True)
class LiquidityUpdated(BaseEvent):
    """Fired when Liquidity metrics are updated."""


@dataclass(frozen=True)
class OrderFlowUpdated(BaseEvent):
    """Fired when Order Flow calculations are updated."""


@dataclass(frozen=True)
class VolumeProfileUpdated(BaseEvent):
    """Fired when Volume Profile calculations are updated."""


@dataclass(frozen=True)
class MarketConfidenceUpdated(BaseEvent):
    """Fired when Market Confidence is updated."""


# Import & re-export to keep local access clean
from toji_platform.core.event_bus.events import MarketIntelligenceCompleted as TojiMarketIntelligenceCompleted

@dataclass(frozen=True)
class MarketIntelligenceCompleted(TojiMarketIntelligenceCompleted):
    """Re-exported market intelligence completed event."""

