"""Unit tests for the Intelligence Report Generator."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from intelligence.models import MarketPulse, Opportunity, RiskGrade
from intelligence.reports.generator import IntelligenceReportGenerator


@pytest.fixture
def generator() -> IntelligenceReportGenerator:
    """Provide an IntelligenceReportGenerator instance."""
    return IntelligenceReportGenerator()


def test_market_intelligence_report(generator: IntelligenceReportGenerator) -> None:
    """Test generating overall market summaries from pulse snapshots."""
    pulses = {
        "BTC/USDT": MarketPulse(
            trend=0.8,
            momentum=0.6,
            liquidity=2.0,
            risk=0.1,
            volatility=0.015,
            participation=1.2,
            fear=30.0,
            confidence=0.9,
            overall_score=0.85,
            timestamp=datetime.now(timezone.utc),
        ),
        "ETH/USDT": MarketPulse(
            trend=0.5,
            momentum=0.3,
            liquidity=1.5,
            risk=0.2,
            volatility=0.02,
            participation=1.0,
            fear=35.0,
            confidence=0.85,
            overall_score=0.72,
            timestamp=datetime.now(timezone.utc),
        ),
    }

    report = generator.generate_market_intelligence_report(pulses)
    assert report["average_overall_score"] == pytest.approx(0.785, 0.01)
    assert report["average_risk_score"] == pytest.approx(0.15, 0.01)
    assert report["total_assets_tracked"] == 2
    assert "BTC/USDT" in report["healthiest_assets"]


def test_opportunity_report(generator: IntelligenceReportGenerator) -> None:
    """Test generating opportunity list summary tables."""
    opps = [
        Opportunity(
            symbol="BTC/USDT",
            strategy_id="strat-1",
            score=0.92,
            regime="Markup",
            timing_window="Immediate",
            risk_grade=RiskGrade.A,
        ),
        Opportunity(
            symbol="ETH/USDT",
            strategy_id="strat-1",
            score=0.76,
            regime="Markup",
            timing_window="Delayed",
            risk_grade=RiskGrade.B,
        ),
    ]

    report = generator.generate_opportunity_report(opps)
    assert report["total_opportunities"] == 2
    assert report["top_opportunity"]["symbol"] == "BTC/USDT"
    assert report["risk_grade_distribution"]["A"] == 1
    assert report["risk_grade_distribution"]["B"] == 1


def test_regime_report(generator: IntelligenceReportGenerator) -> None:
    """Test compiling detected regimes and distributions."""
    regimes = {
        "BTC/USDT": "Markup",
        "ETH/USDT": "Markup",
        "SOL/USDT": "Accumulation",
        "AAPL": "Compression",
    }

    report = generator.generate_regime_report(regimes)
    assert report["total_assets_analyzed"] == 4
    assert report["phase_counts"]["Markup"] == 2
    assert report["phase_counts"]["Accumulation"] == 1
    assert report["phase_distribution_pct"]["Markup"] == 0.5


def test_timing_report(generator: IntelligenceReportGenerator) -> None:
    """Test timing statistics reports."""
    decays = {"BTC/USDT": 0.95, "ETH/USDT": 0.45, "SOL/USDT": 0.20}
    sessions = {"BTC/USDT": "London", "ETH/USDT": "NewYork", "SOL/USDT": "Quiet"}

    report = generator.generate_timing_report(decays, sessions)
    assert report["average_freshness"] == pytest.approx(0.533, 0.01)
    assert report["stale_signals_count"] == 2
    assert report["fresh_signals_count"] == 1


def test_execution_window_report(generator: IntelligenceReportGenerator) -> None:
    """Test compiling window readiness metrics."""
    windows = {"BTC/USDT": "Immediate", "ETH/USDT": "Delayed", "SOL/USDT": "Blocked"}

    report = generator.generate_execution_window_report(windows)
    assert report["total_assets"] == 3
    assert "BTC/USDT" in report["immediate_execution_assets"]
    assert "SOL/USDT" in report["blocked_execution_assets"]
