"""Decision Journal and Timeline manager for logging decisions and auditing correctness."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from decision.models import DecisionState, InvestmentDecision, JournalEntry, TimelineEvent, TimelineState


class DecisionJournal:
    """Manages thread-safe decision registration, timeline lifecycles, and retrospect correctness audits."""

    def __init__(self) -> None:
        """Initialize the DecisionJournal."""
        self._entries: dict[str, JournalEntry] = {}
        self._lock = threading.Lock()

    def log_decision(self, decision: InvestmentDecision) -> JournalEntry:
        """Register a new decision and initiate its timeline history.

        Args:
            decision: InvestmentDecision object.

        Returns:
            The created JournalEntry.
        """
        event = TimelineEvent(
            timestamp=datetime.now(timezone.utc),
            state=TimelineState.CREATED,
            details=f"Decision compiled for symbol {decision.symbol}. Initial recommendation: {decision.final_recommendation.value}",
        )

        entry = JournalEntry(
            decision_id=decision.decision_id,
            decision=decision,
            timeline_history=[event],
        )

        with self._lock:
            self._entries[decision.decision_id] = entry

        return entry

    def update_timeline(self, decision_id: str, state: TimelineState, details: str) -> None:
        """Append a new lifecycle event to a decision's timeline.

        Args:
            decision_id: Target decision ID.
            state: Target TimelineState.
            details: Rationale or audit context for the change.
        """
        now = datetime.now(timezone.utc)
        event = TimelineEvent(timestamp=now, state=state, details=details)

        with self._lock:
            entry = self._entries.get(decision_id)
            if not entry:
                raise ValueError(f"Decision ID '{decision_id}' not found in journal")

            # Create a new list copy to satisfy pydantic frozen elements if any,
            # but since JournalEntry is not frozen, we can append directly.
            entry.timeline_history.append(event)

            # Update closed_at if state marks termination
            if state in (TimelineState.CLOSED, TimelineState.EXPIRED, TimelineState.CANCELLED):
                entry = entry.model_copy(update={"closed_at": now})
                self._entries[decision_id] = entry

    def record_outcome(
        self,
        decision_id: str,
        outcome: str,
        is_correct: bool | None = None,
        lessons: list[str] | None = None,
    ) -> None:
        """Record the post-execution outcome, correctness flag, and lessons learned.

        Args:
            decision_id: Target decision ID.
            outcome: Textual summary of the market outcome.
            is_correct: Optional correctness boolean.
            lessons: List of qualitative retrospect lessons.
        """
        with self._lock:
            entry = self._entries.get(decision_id)
            if not entry:
                raise ValueError(f"Decision ID '{decision_id}' not found in journal")

            updated_lessons = list(entry.lessons)
            if lessons:
                updated_lessons.extend(lessons)

            # Append closed timeline event if not already closed
            already_closed = entry.closed_at is not None
            timeline = list(entry.timeline_history)
            closed_at = entry.closed_at

            if not already_closed:
                closed_at = datetime.now(timezone.utc)
                timeline.append(
                    TimelineEvent(
                        timestamp=closed_at,
                        state=TimelineState.CLOSED,
                        details="Decision marked Closed. Performance outcome recorded.",
                    )
                )

            updated_entry = entry.model_copy(
                update={
                    "outcome": outcome,
                    "is_correct": is_correct,
                    "lessons": updated_lessons,
                    "timeline_history": timeline,
                    "closed_at": closed_at,
                }
            )
            self._entries[decision_id] = updated_entry

    def audit_correctness(self, decision_id: str, prices: list[float]) -> bool | None:
        """Evaluate recommendation correctness against price series delta.

        Rules applied:
        - Long stances (ENTER, READY, PREPARE, HOLD): Correct if prices[-1] > prices[0].
        - Exit stances (EXIT, EMERGENCY_EXIT, REDUCE): Correct if prices[-1] < prices[0] (loss avoided).
        - Ranging/Ignore stances (IGNORE, WATCH): Correct if prices are flat (return < 2% absolute).

        Args:
            decision_id: Target decision ID.
            prices: Historical price series from the decision's lifetime window.

        Returns:
            Boolean correctness outcome, or None if prices are insufficient.
        """
        if len(prices) < 2:
            return None

        with self._lock:
            entry = self._entries.get(decision_id)
            if not entry:
                raise ValueError(f"Decision ID '{decision_id}' not found in journal")

            rec = entry.decision.final_recommendation
            price_start = prices[0]
            price_end = prices[-1]
            pct_return = (price_end - price_start) / price_start

            is_correct = False
            outcome_msg = ""

            if rec in (DecisionState.ENTER, DecisionState.READY, DecisionState.PREPARE, DecisionState.HOLD):
                is_correct = price_end > price_start
                outcome_msg = (
                    f"Long recommendation. Price changed from {price_start} to {price_end} ({pct_return:+.2%}). "
                    f"Outcome correct: {is_correct}"
                )
            elif rec in (DecisionState.EXIT, DecisionState.EMERGENCY_EXIT, DecisionState.REDUCE):
                is_correct = price_end < price_start
                outcome_msg = (
                    f"Exit/Reduce recommendation. Price changed from {price_start} to {price_end} ({pct_return:+.2%}). "
                    f"Risk reduction correct (losses avoided/minimized): {is_correct}"
                )
            else:  # IGNORE, WATCH
                # Correct if market consolidates or falls (no missed opportunity)
                is_correct = abs(pct_return) < 0.02
                outcome_msg = (
                    f"Ignore/Watch recommendation. Price changed from {price_start} to {price_end} ({pct_return:+.2%}). "
                    f"Sideline correct: {is_correct}"
                )

            # Record outcome automatically
            lessons = ["Audited via price delta validation engine."]
            if not is_correct:
                lessons.append("Consensus failed to align with subsequent asset direction.")

            already_closed = entry.closed_at is not None
            timeline = list(entry.timeline_history)
            closed_at = entry.closed_at

            if not already_closed:
                closed_at = datetime.now(timezone.utc)
                timeline.append(
                    TimelineEvent(
                        timestamp=closed_at,
                        state=TimelineState.CLOSED,
                        details="Decision marked Closed. Performance audit recorded.",
                    )
                )

            # Update entry in journal
            # We temporarily release lock logic to avoid re-entry, but since we are modifying, we inline updates
            updated_entry = entry.model_copy(
                update={
                    "outcome": outcome_msg,
                    "is_correct": is_correct,
                    "lessons": list(entry.lessons) + lessons,
                    "timeline_history": timeline,
                    "closed_at": closed_at,
                }
            )
            self._entries[decision_id] = updated_entry

            return is_correct

    def get_entry(self, decision_id: str) -> JournalEntry | None:
        """Retrieve a journal entry.

        Args:
            decision_id: Decision ID.

        Returns:
            JournalEntry or None.
        """
        with self._lock:
            return self._entries.get(decision_id)
