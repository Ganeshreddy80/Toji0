"""Unit tests for the Alpha Decay Tracker."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from intelligence.alpha_decay.tracker import AlphaDecayTracker


@pytest.fixture
def tracker() -> AlphaDecayTracker:
    """Provide an AlphaDecayTracker instance."""
    return AlphaDecayTracker(
        min_history_length=4,
        sharpe_retirement_threshold=0.5,
        win_rate_retirement_threshold=0.45,
        decay_threshold=0.30,
    )


def test_insufficient_history(tracker: AlphaDecayTracker) -> None:
    """Test retirement recommendation check on short history."""
    tracker.record_performance("strat-1", 2.0, 0.6, 0.05)
    report = tracker.evaluate_decay("strat-1")
    assert report["should_retire"] is False
    assert "Insufficient history" in report["reason"]


def test_stable_performance(tracker: AlphaDecayTracker) -> None:
    """Test stable performance runs do not trigger retirement."""
    now = datetime.now(timezone.utc)
    for i in range(5):
        tracker.record_performance(
            "strat-1",
            sharpe=2.0,
            win_rate=0.6,
            returns=0.04,
            timestamp=now - timedelta(days=5 - i),
        )

    report = tracker.evaluate_decay("strat-1")
    assert report["should_retire"] is False
    assert report["decay_rate"] == 0.0
    assert report["sharpe_slope"] == 0.0


def test_sharpe_retirement(tracker: AlphaDecayTracker) -> None:
    """Test retirement triggered by dropping Sharpe ratio."""
    now = datetime.now(timezone.utc)
    # Performance dropping sharply
    sharpes = [2.2, 1.8, 1.2, 0.7, 0.3]
    for i, s in enumerate(sharpes):
        tracker.record_performance(
            "strat-1",
            sharpe=s,
            win_rate=0.6,
            returns=0.01,
            timestamp=now - timedelta(days=5 - i),
        )

    report = tracker.evaluate_decay("strat-1")
    assert report["should_retire"] is True
    assert "Sharpe ratio" in report["reason"]


def test_win_rate_retirement(tracker: AlphaDecayTracker) -> None:
    """Test retirement triggered by dropping win rate."""
    now = datetime.now(timezone.utc)
    # Win rate dropping below 45% (recent average will be (0.55 + 0.30 + 0.25)/3 = 0.3667 < 0.45)
    win_rates = [0.65, 0.60, 0.55, 0.30, 0.25]
    for i, w in enumerate(win_rates):
        tracker.record_performance(
            "strat-1",
            sharpe=1.5,
            win_rate=w,
            returns=0.01,
            timestamp=now - timedelta(days=5 - i),
        )

    report = tracker.evaluate_decay("strat-1")
    assert report["should_retire"] is True
    assert "Win rate" in report["reason"]


def test_percentage_decay_retirement(tracker: AlphaDecayTracker) -> None:
    """Test retirement triggered by Sharpe decaying more than 30% from baseline."""
    now = datetime.now(timezone.utc)
    # Baseline average: (2.0 + 2.0 + 2.0) / 3 = 2.0
    # Decayed Sharpe: recent average is (2.0 + 0.9 + 0.7)/3 = 1.2 (a 40% decay, which is > 30% threshold)
    sharpes = [2.0, 2.0, 2.0, 0.9, 0.7]
    for i, s in enumerate(sharpes):
        tracker.record_performance(
            "strat-1",
            sharpe=s,
            win_rate=0.6,
            returns=0.01,
            timestamp=now - timedelta(days=5 - i),
        )

    report = tracker.evaluate_decay("strat-1")
    assert report["should_retire"] is True
    assert "decayed by" in report["reason"]
