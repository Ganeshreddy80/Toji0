"""Timing Committee implementation for evaluating window readiness and regimes."""

from __future__ import annotations

from typing import Any
from decision.committees.base import BaseCommittee
from decision.models import CommitteeVote, DecisionState


class TimingCommittee(BaseCommittee):
    """Evaluates signal freshness, market sessions, event proximity offsets, and regime alignment."""

    def vote(self, context: dict[str, Any]) -> CommitteeVote:
        """Evaluate timing criteria and submit a vote.

        Args:
            context: Context containing 'timing_window', 'signal_age_seconds',
                     'event_proximity_seconds', 'regime_aligned', and 'session'.

        Returns:
            CommitteeVote.
        """
        window = context.get("timing_window", "Immediate").strip().lower()
        age_sec = context.get("signal_age_seconds", 0.0)
        event_prox = context.get("event_proximity_seconds", float("inf"))
        regime_aligned = context.get("regime_aligned", True)
        session = context.get("session", "London")

        metrics = {
            "timing_window": window,
            "signal_age_seconds": age_sec,
            "event_proximity_seconds": event_prox,
            "regime_aligned": regime_aligned,
            "session": session,
        }

        # Blocked / Event risk -> IGNORE or WATCH to block execution
        if window == "blocked" or event_prox < 300.0:
            return CommitteeVote(
                committee_name="Timing",
                vote_state=DecisionState.IGNORE,
                score=0.0,
                confidence=0.95,
                metrics=metrics,
                reason="Execution blocked due to close proximity of scheduled macroeconomic events",
            )

        # Expired signals
        if window == "expired" or age_sec > 7200.0:
            return CommitteeVote(
                committee_name="Timing",
                vote_state=DecisionState.IGNORE,
                score=0.0,
                confidence=0.90,
                metrics=metrics,
                reason=f"Signal expired due to age ({age_sec:.0f} seconds elapsed)",
            )

        # Regime mismatch
        if not regime_aligned:
            return CommitteeVote(
                committee_name="Timing",
                vote_state=DecisionState.IGNORE,
                score=0.0,
                confidence=0.85,
                metrics=metrics,
                reason="Strategy mismatch with current detected market regime phase",
            )

        # Deferred execution window (e.g. quiet session)
        if window == "deferred" or session.lower() == "quiet":
            return CommitteeVote(
                committee_name="Timing",
                vote_state=DecisionState.WATCH,
                score=0.20,
                confidence=0.80,
                metrics=metrics,
                reason=f"Execution deferred due to quiet market session ({session})",
            )

        # Delayed execution (e.g. wait for pullback)
        if window == "delayed":
            return CommitteeVote(
                committee_name="Timing",
                vote_state=DecisionState.PREPARE,
                score=0.50,
                confidence=0.80,
                metrics=metrics,
                reason="Signal valid but timing window suggests waiting for pullback/re-entry",
            )

        # Optimal timing
        return CommitteeVote(
            committee_name="Timing",
            vote_state=DecisionState.ENTER,
            score=0.95,
            confidence=0.90,
            metrics=metrics,
            reason="Optimal execution timing window (Immediate) and session active",
        )
