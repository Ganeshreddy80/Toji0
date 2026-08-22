"""Unit tests for the Investment Committee Voting Engine."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from decision.models import DecisionState
from decision.voting.engine import InvestmentCommittee


@pytest.fixture
def ic() -> InvestmentCommittee:
    """Provide an InvestmentCommittee instance."""
    return InvestmentCommittee()


@pytest.fixture
def healthy_context() -> dict[str, Any]:
    """Provide context for a healthy entry consensus."""
    return {
        "win_rate": 0.65,
        "sharpe": 2.5,
        "p_value": 0.005,
        "t_stat": 3.2,
        "experiment_validation": "passed",
        "backtest_robustness_score": 0.90,
        "returns": [0.01, 0.02, -0.01],
        "equity_series": [100.0, 101.0, 102.0],
        "positions_value": {"BTC/USDT": 1000.0},
        "total_equity": 100000.0,
        "win_rate": 0.60,
        "payoff_ratio": 2.0,
        "fraction_risked": 0.01,
        "concentration_pct": 0.01,
        "average_correlation": 0.20,
        "suggested_allocation_pct": 0.05,
        "timing_window": "Immediate",
        "signal_age_seconds": 10.0,
        "event_proximity_seconds": 3600.0,
        "regime_aligned": True,
        "session": "London",
        "rule_confidence_weight": 0.85,
        "evidence_count": 3,
        "active_contradictions_count": 0,
        "knowledge_freshness": 0.90,
    }


def test_compile_decision_consensus(ic: InvestmentCommittee, healthy_context: dict[str, Any]) -> None:
    """Test standard decision compile where all committees agree on entering."""
    now = datetime.now(timezone.utc)
    decision = ic.compile_decision("BTC/USDT", healthy_context, regime="markup", evaluation_time=now)

    assert decision.symbol == "BTC/USDT"
    assert decision.final_recommendation == DecisionState.ENTER
    assert decision.overall_score >= 0.80
    assert decision.confidence >= 0.80
    assert len(decision.votes) == 5
    assert decision.created_at == now


def test_emergency_exit_veto(ic: InvestmentCommittee, healthy_context: dict[str, Any]) -> None:
    """Test Risk committee vetoing with EMERGENCY_EXIT when drawdown is breached."""
    context_veto = dict(healthy_context)
    # Trigger 20% drawdown breach
    context_veto["equity_series"] = [100.0, 80.0]

    decision = ic.compile_decision("BTC/USDT", context_veto, regime="markup")

    # Even though other committees are bullish, Risk EMERGENCY_EXIT vetoes the consensus!
    assert decision.final_recommendation == DecisionState.EMERGENCY_EXIT
    assert decision.overall_score == -1.0
    assert "Veto triggered" in decision.risk_summary


def test_regime_weights_profile(ic: InvestmentCommittee, healthy_context: dict[str, Any]) -> None:
    """Verify that different regime profiles yield different scores due to weights scaling."""
    # Under expansion, Risk weight is 0.45.
    # Let's create a context where Risk is neutral/cautious (votes REDUCE) but others are ENTER.
    context_mixed = dict(healthy_context)
    # Approach exposure limits -> Risk votes REDUCE (score=0.20)
    context_mixed["gross_exposure"] = 1.6
    context_mixed["positions_value"] = {"BTC/USDT": 160000.0}
    context_mixed["total_equity"] = 100000.0

    # Default profile vs expansion profile
    dec_default = ic.compile_decision("BTC/USDT", context_mixed, regime="default")
    dec_expansion = ic.compile_decision("BTC/USDT", context_mixed, regime="expansion")

    # Since Risk has higher weight in expansion, the overall score under expansion should be lower
    # than default because Risk voted REDUCE (score=0.20).
    assert dec_expansion.overall_score < dec_default.overall_score
