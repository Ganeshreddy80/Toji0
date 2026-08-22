"""System events for the Price Action Engine.

All events are frozen dataclasses inheriting from BaseEvent.
"""

from __future__ import annotations

from dataclasses import dataclass

from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class PriceActionInitialized(BaseEvent):
    """Fired when the Price Action Engine plugin starts successfully."""


@dataclass(frozen=True)
class PriceActionShutdown(BaseEvent):
    """Fired when the Price Action Engine plugin shuts down."""


@dataclass(frozen=True)
class PatternDetected(BaseEvent):
    """Fired when a new candidate pattern is first detected.

    Payload should contain keys:
        symbol: str
        timeframe: str
        candidate: dict representing the serialized PatternCandidate.
    """


@dataclass(frozen=True)
class PatternUpdated(BaseEvent):
    """Fired when a candidate or active pattern is updated.

    Payload should contain keys:
        symbol: str
        timeframe: str
        pattern_id: str
        status: str
        pattern: dict representing the serialized PatternCandidate or PatternMatch.
    """


@dataclass(frozen=True)
class PatternConfirmed(BaseEvent):
    """Fired when a candidate pattern transitions to CONFIRMED.

    Payload should contain keys:
        symbol: str
        timeframe: str
        match: dict representing the serialized PatternMatch.
    """


@dataclass(frozen=True)
class PatternInvalidated(BaseEvent):
    """Fired when a pattern transitions to INVALIDATED.

    Payload should contain keys:
        symbol: str
        timeframe: str
        match: dict representing the serialized PatternMatch.
    """


@dataclass(frozen=True)
class PatternCompleted(BaseEvent):
    """Fired when a confirmed pattern transitions to COMPLETED.

    Payload should contain keys:
        symbol: str
        timeframe: str
        match: dict representing the serialized PatternMatch.
    """


@dataclass(frozen=True)
class PatternQualityUpdated(BaseEvent):
    """Fired when the quality assessment of a candidate or match is updated.

    Payload should contain keys:
        symbol: str
        timeframe: str
        pattern_id: str
        status: str  # DEVELOPING, CONFIRMED, etc.
        quality: dict representing the serialized PatternQuality.
    """


@dataclass(frozen=True)
class PriceActionUpdated(BaseEvent):
    """Fired when price action features or timeframe state updates."""


@dataclass(frozen=True)
class PriceActionGenerated(BaseEvent):
    """Fired when a new multi-timeframe price action snapshot is generated."""


@dataclass(frozen=True)
class PriceActionFailed(BaseEvent):
    """Fired when price action analysis encounters invalid data or runtime error and fails closed."""


@dataclass(frozen=True)
class PriceActionAnalysisCompleted(BaseEvent):
    """Fired when full price action evaluation completes successfully for a symbol."""


