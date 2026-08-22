"""Unit tests for the Opportunity Engine."""

from __future__ import annotations

import pytest
from intelligence.models import RiskGrade
from intelligence.opportunities.engine import OpportunityEngine


@pytest.fixture
def engine() -> OpportunityEngine:
    """Provide a fresh OpportunityEngine instance."""
    return OpportunityEngine(
        weight_analytics=0.4,
        weight_timing=0.2,
        weight_risk=0.2,
        weight_knowledge=0.2,
    )


def test_evaluate_opportunity(engine: OpportunityEngine) -> None:
    """Test opportunity scoring metrics are calculated correctly."""
    opp = engine.evaluate_opportunity(
        symbol="BTC/USDT",
        strategy_id="strat-1",
        regime="Markup",
        timing_window="Immediate",
        win_rate=0.6,
        sharpe=2.0,
        timing_decay=0.9,
        risk_grade=RiskGrade.A,
        evidence_count=3,
    )

    assert opp.symbol == "BTC/USDT"
    assert opp.strategy_id == "strat-1"
    assert opp.regime == "Markup"
    assert opp.timing_window == "Immediate"
    assert opp.risk_grade == RiskGrade.A
    assert opp.evidence_count == 3
    assert 0.0 <= opp.score <= 1.0


def test_rank_opportunities(engine: OpportunityEngine) -> None:
    """Test ordering of opportunity lists."""
    opp1 = engine.evaluate_opportunity(
        symbol="BTC/USDT",
        strategy_id="strat-1",
        regime="Markup",
        timing_window="Immediate",
        win_rate=0.5,
        sharpe=1.0,
        timing_decay=0.5,
        risk_grade=RiskGrade.C,
        evidence_count=1,
    )

    opp2 = engine.evaluate_opportunity(
        symbol="ETH/USDT",
        strategy_id="strat-1",
        regime="Markup",
        timing_window="Immediate",
        win_rate=0.8,
        sharpe=2.8,
        timing_decay=0.95,
        risk_grade=RiskGrade.A,
        evidence_count=5,
    )

    ranked = engine.rank_opportunities([opp1, opp2])
    assert len(ranked) == 2
    assert ranked[0].symbol == "ETH/USDT"  # High stats should rank first
    assert ranked[1].symbol == "BTC/USDT"
