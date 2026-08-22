"""Timing Engine for signal freshness and execution window support."""

from __future__ import annotations

import math
from datetime import datetime, timezone


class TimingEngine:
    """Evaluates signal aging, market session filters, event proximity, and optimal execution windows."""

    def __init__(
        self,
        half_life_seconds: float = 3600.0,  # 1 hour decay half-life
        max_age_seconds: float = 7200.0,    # 2 hours max age
        event_buffer_seconds: float = 900.0, # 15 minutes event buffer
    ) -> None:
        """Initialize the TimingEngine.

        Args:
            half_life_seconds: Signal half-life decay parameter.
            max_age_seconds: Maximum age before a signal is expired.
            event_buffer_seconds: Safe buffer around macro events.
        """
        self.half_life_seconds = half_life_seconds
        self.max_age_seconds = max_age_seconds
        self.event_buffer_seconds = event_buffer_seconds
        # Calculate decay constant lambda: ln(2) / half_life
        self._lambda = math.log(2.0) / half_life_seconds

    def calculate_signal_decay(self, signal_time: datetime, current_time: datetime | None = None) -> float:
        """Calculate signal freshness multiplier from 1.0 (fresh) down to 0.0 (fully decayed).

        Args:
            signal_time: Time the signal was generated.
            current_time: Evaluation time. Defaults to now.

        Returns:
            Decay factor from 0.0 to 1.0.
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Ensure both are timezone aware or both are naive
        if signal_time.tzinfo is None and current_time.tzinfo is not None:
            signal_time = signal_time.replace(tzinfo=timezone.utc)
        elif signal_time.tzinfo is not None and current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        age_seconds = (current_time - signal_time).total_seconds()
        if age_seconds < 0.0:
            return 1.0  # Future signal (testing mock edge case)
        if age_seconds > self.max_age_seconds:
            return 0.0

        return math.exp(-self._lambda * age_seconds)

    def get_market_session(self, timestamp: datetime) -> str:
        """Classify the current market session based on UTC hour of timestamp.

        Args:
            timestamp: The datetime to evaluate.

        Returns:
            Session name: 'Asia', 'London', 'NewYork', 'Overlap', or 'Quiet'.
        """
        hour = timestamp.astimezone(timezone.utc).hour
        # London: 08:00 - 16:00 UTC
        # New York: 13:00 - 21:00 UTC
        # Asia: 00:00 - 08:00 UTC
        if 13 <= hour < 16:
            return "Overlap"  # London & NY overlap
        elif 8 <= hour < 13:
            return "London"
        elif 16 <= hour < 21:
            return "NewYork"
        elif 0 <= hour < 8:
            return "Asia"
        else:
            return "Quiet"

    def get_event_proximity(
        self,
        evaluation_time: datetime,
        event_times: list[datetime],
    ) -> tuple[float, bool]:
        """Compute distance to the closest macroeconomic event and check if inside unsafe buffer.

        Args:
            evaluation_time: Reference time.
            event_times: List of calendar event datetimes.

        Returns:
            Tuple of (min_offset_seconds, is_within_unsafe_buffer).
        """
        if not event_times:
            return float("inf"), False

        # Normalize evaluation_time to timezone aware if lists are timezone aware
        if evaluation_time.tzinfo is None and any(e.tzinfo is not None for e in event_times):
            evaluation_time = evaluation_time.replace(tzinfo=timezone.utc)

        min_offset = float("inf")
        for event in event_times:
            if event.tzinfo is None and evaluation_time.tzinfo is not None:
                event = event.replace(tzinfo=timezone.utc)
            elif event.tzinfo is not None and evaluation_time.tzinfo is None:
                evaluation_time = evaluation_time.replace(tzinfo=timezone.utc)

            offset = abs((event - evaluation_time).total_seconds())
            if offset < min_offset:
                min_offset = offset

        is_unsafe = min_offset < self.event_buffer_seconds
        return min_offset, is_unsafe

    def determine_execution_window(
        self,
        signal_time: datetime,
        evaluation_time: datetime,
        event_times: list[datetime] | None = None,
        is_crypto: bool = True,
    ) -> str:
        """Analyze timing criteria to recommend an execution window.

        Args:
            signal_time: Time signal was generated.
            evaluation_time: Reference time.
            event_times: List of scheduled event times.
            is_crypto: Whether the asset trades 24/7.

        Returns:
            Execution window: 'Immediate', 'Delayed', 'Deferred', 'Expired', or 'Blocked'.
        """
        # 1. Freshness check
        decay = self.calculate_signal_decay(signal_time, evaluation_time)
        if decay <= 0.0:
            return "Expired"

        # 2. Event proximity check
        if event_times:
            _, is_unsafe = self.get_event_proximity(evaluation_time, event_times)
            if is_unsafe:
                return "Blocked"

        # 3. Market Session check for non-24/7 assets
        if not is_crypto:
            session = self.get_market_session(evaluation_time)
            if session == "Quiet":
                return "Deferred"

        # 4. Decayed/Aged Signal - Recommend delay/pullback check
        if decay < 0.7:
            return "Delayed"

        return "Immediate"
