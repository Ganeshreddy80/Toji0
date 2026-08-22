"""Unit tests for the Specialized Committees."""

from __future__ import annotations

import pytest
from decision.models import DecisionState
from decision.committees import (
    ResearchCommittee,
    RiskCommittee,
    PortfolioCommittee,
    TimingCommittee,
    KnowledgeCommittee,
)


def test_research_committee_voting() -> None:
    """Test Research Committee vote logic across stats distributions."""
    committee = ResearchCommittee()

    # Premium parameters -> ENTER
    context_enter = {
        "win_rate": 0.65,
        "sharpe": 2.5,
        "p_value": 0.005,
        "t_stat": 3.2,
        "experiment_validation": "passed",
        "backtest_robustness_score": 0.90,
    }
    vote = committee.vote(context_enter)
    assert vote.vote_state == DecisionState.ENTER
    assert vote.score == 0.95
    assert vote.confidence == 0.90

    # Weak Sharpe -> WATCH
    context_watch = {
        "win_rate": 0.50,
        "sharpe": 0.9,
        "p_value": 0.04,
        "t_stat": 2.1,
        "experiment_validation": "passed",
        "backtest_robustness_score": 0.70,
    }
    vote_watch = committee.vote(context_watch)
    assert vote_watch.vote_state == DecisionState.WATCH

    # Validation failed -> EXIT
    context_fail = {
        "win_rate": 0.60,
        "sharpe": 2.0,
        "p_value": 0.01,
        "t_stat": 2.5,
        "experiment_validation": "failed",
    }
    vote_fail = committee.vote(context_fail)
    assert vote_fail.vote_state == DecisionState.EXIT


def test_risk_committee_voting() -> None:
    """Test Risk Committee drawdown, VaR, and ruin limits voting."""
    committee = RiskCommittee(
        default_max_drawdown=0.10,
        default_max_var=0.03,
        default_max_ruin_prob=0.05,
    )

    # Clean risk -> ENTER
    context_clean = {
        "returns": [0.01, 0.02, -0.01, 0.01, 0.01],
        "equity_series": [100.0, 101.0, 102.0, 101.5, 102.5],
        "positions_value": {"BTC/USDT": 10000.0},
        "total_equity": 100000.0,
        "win_rate": 0.60,
        "payoff_ratio": 2.0,
        "fraction_risked": 0.01,
    }
    vote = committee.vote(context_clean)
    assert vote.vote_state == DecisionState.ENTER
    assert vote.metrics["current_drawdown"] < 0.05

    # Drawdown limit breach -> EMERGENCY_EXIT
    context_breach = dict(context_clean)
    # peak 100, trough 85 -> 15% drawdown (limit is 10%)
    context_breach["equity_series"] = [100.0, 85.0, 86.0]
    vote_breach = committee.vote(context_breach)
    assert vote_breach.vote_state == DecisionState.EMERGENCY_EXIT


def test_portfolio_committee_voting() -> None:
    """Test Portfolio Committee concentration and correlation checks."""
    committee = PortfolioCommittee(max_concentration_limit=0.10, max_correlation_limit=0.70)

    # Safe -> ENTER
    context_safe = {
        "concentration_pct": 0.05,
        "average_correlation": 0.30,
        "suggested_allocation_pct": 0.06,
    }
    vote = committee.vote(context_safe)
    assert vote.vote_state == DecisionState.ENTER

    # Concentration breach -> REDUCE
    context_conc = dict(context_safe)
    context_conc["concentration_pct"] = 0.12
    vote_conc = committee.vote(context_conc)
    assert vote_conc.vote_state == DecisionState.REDUCE


def test_timing_committee_voting() -> None:
    """Test Timing Committee execution state checks."""
    committee = TimingCommittee()

    # Immediate -> ENTER
    context_immediate = {
        "timing_window": "Immediate",
        "signal_age_seconds": 120.0,
        "event_proximity_seconds": 3600.0,
        "regime_aligned": True,
        "session": "London",
    }
    vote = committee.vote(context_immediate)
    assert vote.vote_state == DecisionState.ENTER

    # Blocked by macro event -> IGNORE
    context_blocked = dict(context_immediate)
    context_blocked["timing_window"] = "Blocked"
    vote_blocked = committee.vote(context_blocked)
    assert vote_blocked.vote_state == DecisionState.IGNORE


def test_knowledge_committee_voting() -> None:
    """Test Knowledge Committee contradictions and evidence volume checks."""
    committee = KnowledgeCommittee()

    # Highly supported, no conflict -> ENTER
    context_good = {
        "rule_confidence_weight": 0.85,
        "evidence_count": 4,
        "active_contradictions_count": 0,
        "knowledge_freshness": 0.90,
    }
    vote = committee.vote(context_good)
    assert vote.vote_state == DecisionState.ENTER

    # Active conflict -> IGNORE
    context_conflict = dict(context_good)
    context_conflict["active_contradictions_count"] = 1
    vote_conflict = committee.vote(context_conflict)
    assert vote_conflict.vote_state == DecisionState.IGNORE
