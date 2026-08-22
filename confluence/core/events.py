"""System events for the Confluence Engine.

All events are frozen dataclasses inheriting from BaseEvent.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class ConfluenceInitialized(BaseEvent):
    """Fired when the Confluence Engine plugin starts successfully."""


@dataclass(frozen=True)
class ConfluenceShutdown(BaseEvent):
    """Fired when the Confluence Engine plugin shuts down."""


@dataclass(frozen=True)
class ConfluenceUpdated(BaseEvent):
    """Fired when confluence scoring is calculated or updated.

    Payload should contain:
        symbol: str
        timeframe: str
        state: dict representing the serialized ConfluenceState.
    """


@dataclass(frozen=True)
class SetupDetected(BaseEvent):
    """Fired when a high-grade setup (A+, A, B+, or B) is detected.

    Payload should contain:
        symbol: str
        timeframe: str
        state: dict representing the serialized ConfluenceState.
    """


@dataclass(frozen=True)
class SetupRejected(BaseEvent):
    """Fired when a confluence grade falls below C (No Trade status).

    Payload should contain:
        symbol: str
        timeframe: str
        state: dict representing the serialized ConfluenceState.
    """


@dataclass(frozen=True)
class SetupGradeChanged(BaseEvent):
    """Fired when the grade transitions (e.g. B -> A).

    Payload should contain:
        symbol: str
        timeframe: str
        old_grade: str
        new_grade: str
        state: dict representing the serialized ConfluenceState.
    """


# Sprint 6: New dedicated events

@dataclass(frozen=True)
class ConfluenceScoreUpdated(BaseEvent):
    """Fired on every confluence score recalculation.

    Payload should contain:
        symbol: str
        timeframe: str
        overall_score: float
        grade: str
    """


@dataclass(frozen=True)
class TradeGradeUpdated(BaseEvent):
    """Fired when the trade grade changes.

    Payload should contain:
        symbol: str
        timeframe: str
        old_grade: str
        new_grade: str
    """


@dataclass(frozen=True)
class OpportunityUpdated(BaseEvent):
    """Fired when the opportunity score is updated.

    Payload should contain:
        symbol: str
        timeframe: str
        opportunity_score: float
        setup_quality: float
        execution_quality: float
        expected_rr: float
    """
