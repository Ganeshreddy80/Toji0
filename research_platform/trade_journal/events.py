"""Domain events for the Institutional Trade Journal.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class TradeJournalCreated(BaseEvent):
    """Fired when a completed trade journal is recorded."""
    pass


@dataclass(frozen=True)
class TradeReviewed(BaseEvent):
    """Fired when an AI review completes for a trade journal."""
    pass


@dataclass(frozen=True)
class TradeLessonLearned(BaseEvent):
    """Fired when a trade lesson is logged to database patterns."""
    pass


@dataclass(frozen=True)
class TradeStatisticsUpdated(BaseEvent):
    """Fired when portfolio-wide statistics recalculate."""
    pass
