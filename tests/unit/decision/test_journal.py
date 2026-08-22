"""Unit tests for the Decision Journal, Timeline, and Reports Generator."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from decision.models import CommitteeVote, DecisionState, InvestmentDecision, TimelineState
from decision.journal.manager import DecisionJournal
from decision.reports.generator import DecisionReportGenerator


@pytest.fixture
def journal() -> DecisionJournal:
    """Provide a DecisionJournal instance."""
    return DecisionJournal()


@pytest.fixture
def sample_decision() -> InvestmentDecision:
    """Provide a mock InvestmentDecision."""
    votes = [
        CommitteeVote(
            committee_name="Research",
            vote_state=DecisionState.ENTER,
            score=0.90,
            confidence=0.90,
            reason="Stats support",
        )
    ]
    return InvestmentDecision(
        decision_id="dec-test",
        symbol="BTC/USDT",
        overall_score=0.90,
        final_recommendation=DecisionState.ENTER,
        confidence=0.90,
        votes=votes,
        risk_summary="Safe",
        timing_summary="Immediate",
        expiry_time=datetime.now(timezone.utc),
        review_time=datetime.now(timezone.utc),
    )


def test_log_decision_and_timeline(journal: DecisionJournal, sample_decision: InvestmentDecision) -> None:
    """Test registering decision and advancing timeline lifecycles."""
    entry = journal.log_decision(sample_decision)

    assert entry.decision_id == "dec-test"
    assert len(entry.timeline_history) == 1
    assert entry.timeline_history[0].state == TimelineState.CREATED

    # Update timeline to Executed
    journal.update_timeline("dec-test", TimelineState.EXECUTED, "Executed order filled")
    entry_updated = journal.get_entry("dec-test")
    assert entry_updated is not None
    assert len(entry_updated.timeline_history) == 2
    assert entry_updated.timeline_history[1].state == TimelineState.EXECUTED


def test_correctness_audits(journal: DecisionJournal, sample_decision: InvestmentDecision) -> None:
    """Test price delta correctness audits for different states."""
    # Test 1: ENTER with price rising -> Correct
    journal.log_decision(sample_decision)
    is_correct = journal.audit_correctness("dec-test", [100.0, 105.0])
    assert is_correct is True
    entry = journal.get_entry("dec-test")
    assert entry is not None
    assert entry.is_correct is True
    assert "Outcome correct: True" in entry.outcome

    # Test 2: EXIT with price falling -> Correct
    exit_votes = [
        CommitteeVote(
            committee_name="Risk",
            vote_state=DecisionState.EXIT,
            score=-0.5,
            confidence=0.9,
            reason="Max drawdown",
        )
    ]
    exit_decision = InvestmentDecision(
        decision_id="dec-exit",
        symbol="ETH/USDT",
        overall_score=-0.5,
        final_recommendation=DecisionState.EXIT,
        confidence=0.9,
        votes=exit_votes,
        risk_summary="Breached",
        timing_summary="Immediate",
        expiry_time=datetime.now(timezone.utc),
        review_time=datetime.now(timezone.utc),
    )

    journal.log_decision(exit_decision)
    is_correct_exit = journal.audit_correctness("dec-exit", [100.0, 90.0])
    assert is_correct_exit is True
    entry_exit = journal.get_entry("dec-exit")
    assert entry_exit is not None
    assert entry_exit.is_correct is True
    assert "Risk reduction correct" in entry_exit.outcome


def test_compile_journal_report(journal: DecisionJournal, sample_decision: InvestmentDecision) -> None:
    """Test generating aggregated reports from logged entries."""
    generator = DecisionReportGenerator()

    # Log and audit a correct decision
    journal.log_decision(sample_decision)
    journal.audit_correctness("dec-test", [100.0, 105.0])

    report = generator.compile_journal_report(journal)
    assert report["total_decisions"] == 1
    assert report["correct_decisions"] == 1
    assert report["correctness_ratio"] == 1.0
    assert report["recommendation_distribution"]["ENTER"] == 1
