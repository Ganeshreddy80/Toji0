"""Abstract interfaces for the Market Intelligence Layer."""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Any

from market_intelligence.core.models import (
    ConfidenceState,
    ContextState,
    MarketSnapshot,
    MarketState,
    StoryState,
)


class IMarketIntelligenceEngine(abc.ABC):
    """Contract for analytical sub-engines of the MIL."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Name of the analytical engine."""

    @abc.abstractmethod
    def analyze(self, snapshot: MarketSnapshot) -> MarketState:
        """Process a market snapshot to produce or update the market state.

        Args:
            snapshot: The input market snapshot.

        Returns:
            The analyzed and enriched MarketState.
        """


class IRepository(abc.ABC):
    """Contract for persisting and loading market intelligence snapshots."""

    @abc.abstractmethod
    def save_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Persist a market snapshot.

        Args:
            snapshot: The snapshot to persist.
        """

    @abc.abstractmethod
    def load_snapshot(self, snapshot_id: str) -> MarketSnapshot | None:
        """Load a specific market snapshot by its unique ID.

        Args:
            snapshot_id: Unique snapshot identifier.

        Returns:
            The loaded MarketSnapshot, or None if not found.
        """

    @abc.abstractmethod
    def load_latest_snapshot(self, symbol: str) -> MarketSnapshot | None:
        """Load the most recent snapshot for a given symbol.

        Args:
            symbol: Target ticker symbol.

        Returns:
            The latest MarketSnapshot, or None if none exists.
        """

    @abc.abstractmethod
    def get_historical_snapshots(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MarketSnapshot]:
        """Load historical snapshots for a symbol over a specific timeframe.

        Args:
            symbol: Target ticker symbol.
            start: Start boundary timestamp.
            end: End boundary timestamp.

        Returns:
            List of matching snapshots sorted by timestamp.
        """


class IStateStore(abc.ABC):
    """Contract for in-memory, thread-safe MIL state tracking."""

    @abc.abstractmethod
    def get_snapshot(self, symbol: str) -> MarketSnapshot | None:
        """Retrieve the current state snapshot for a symbol.

        Args:
            symbol: Target ticker symbol.

        Returns:
            The current MarketSnapshot, or None if not initialized.
        """

    @abc.abstractmethod
    def update_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Update the active state snapshot in a thread-safe manner.

        Args:
            snapshot: The new snapshot to set.
        """

    @abc.abstractmethod
    def get_history(self, symbol: str, limit: int = 100) -> list[MarketSnapshot]:
        """Retrieve in-memory history of snapshots for a symbol.

        Args:
            symbol: Target ticker symbol.
            limit: Maximum snapshots to return.

        Returns:
            List of snapshots sorted chronologically.
        """

    @abc.abstractmethod
    def clear(self) -> None:
        """Purge all tracked states from memory."""


class IStoryGenerator(abc.ABC):
    """Contract for generating market structure narratives."""

    @abc.abstractmethod
    def generate_story(self, snapshot: MarketSnapshot) -> StoryState:
        """Generate a narrative story based on market context and events.

        Args:
            snapshot: The context snapshot.

        Returns:
            A StoryState containing the narrative and event history.
        """


class IConfidenceCalculator(abc.ABC):
    """Contract for computing quantitative confidence scores."""

    @abc.abstractmethod
    def calculate_confidence(self, snapshot: MarketSnapshot) -> ConfidenceState:
        """Compute structural model and data confidence metrics.

        Args:
            snapshot: The state snapshot.

        Returns:
            A ConfidenceState containing scores and factor metrics.
        """


class IContextEngine(abc.ABC):
    """Contract for synthesizing unified market context."""

    @abc.abstractmethod
    def evaluate_context(self, snapshot: MarketSnapshot) -> ContextState:
        """Synthesize low-level indicators into unified market phases and key levels.

        Args:
            snapshot: The state snapshot.

        Returns:
            A ContextState summarizing the unified context.
        """


class ISnapshotProvider(abc.ABC):
    """Contract for components capable of supplying or constructing state snapshots."""

    @abc.abstractmethod
    def capture_snapshot(self, symbol: str, data: dict[str, Any]) -> MarketSnapshot:
        """Create a full snapshot capturing all current timeframe states.

        Args:
            symbol: Target ticker symbol.
            data: Arbitrary inputs or updates to inject.

        Returns:
            The captured MarketSnapshot.
        """
