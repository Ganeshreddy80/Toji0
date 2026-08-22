"""Unit tests for the AI Quant Intelligence Engine.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.ai_intelligence.context import AIContextBuilder
from research_platform.ai_intelligence.explanation import ExplanationEngine
from research_platform.ai_intelligence.journal import TradingJournal
from research_platform.ai_intelligence.memory import AIMemory
from research_platform.ai_intelligence.models import Insight, Warning
from research_platform.ai_intelligence.orchestrator import AIIntelligenceOrchestrator
from research_platform.ai_intelligence.performance_analyzer import PerformanceAnalyzer
from research_platform.ai_intelligence.portfolio_reviewer import PortfolioReviewer
from research_platform.ai_intelligence.prompt_builder import PromptBuilder
from research_platform.ai_intelligence.provider import MockLLMProvider
from research_platform.ai_intelligence.recommendation import RecommendationEngine
from research_platform.ai_intelligence.regime_reasoner import MarketRegimeReasoner
from research_platform.ai_intelligence.report_generator import ReportGenerator
from research_platform.ai_intelligence.risk_reviewer import RiskReviewer
from research_platform.ai_intelligence.strategy_reviewer import StrategyReviewer
from research_platform.ai_intelligence.trade_reviewer import TradeReviewer


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return AIIntelligenceOrchestrator(event_bus)


def test_context_gathering():
    """Verify aggregated context has default parameters."""
    builder = AIContextBuilder()
    ctx = builder.gather_context()
    assert ctx["portfolio_value"] == 100000.0
    assert ctx["system_healthy"] is True


def test_memory_sliding_retention():
    """Verify memory retains events and respects retention windows bounds."""
    mem = AIMemory(retention_limit=2)
    mem.record_event("trades", "trade_1")
    mem.record_event("trades", "trade_2")
    mem.record_event("trades", "trade_3")

    events = mem.get_events("trades")
    assert len(events) == 2
    assert "trade_1" not in events
    assert "trade_3" in events


def test_prompt_construction():
    """Verify prompt generates formatted system/user instructions."""
    context = {"portfolio_value": 100000.0, "net_exposure": 0.5, "var_utilization": 0.65, "open_alerts_count": 0, "system_healthy": True}
    req = PromptBuilder.build_review_prompt(context, task="risk_audit")
    assert "risk_audit" in req.prompt
    assert "System Health: True" in req.prompt


def test_llm_provider_generation():
    """Verify mock provider generates text advisory answers."""
    provider = MockLLMProvider()
    req = PromptBuilder.build_review_prompt({"portfolio_value": 100.0}, task="test")
    res = provider.generate_text(req)
    assert "Advisory" in res.text
    assert len(res.reasoning_chain) > 0


def test_strategy_reviews():
    """Verify strategy Sharpe/Sortino checks log suggestions."""
    reviewer = StrategyReviewer()
    
    # Low Sortino, high drawdown -> suggestions generated
    res = reviewer.review_strategy(strategy_id="strat_1", sharpe=1.0, sortino=1.0, drawdown=0.20)
    assert len(res.weaknesses) == 2
    assert any(s.action == "Reduce position size" for s in res.suggestions)
    assert any(s.action == "Tighten Stop Loss" for s in res.suggestions)


def test_trade_reviews():
    """Verify slippage and entry quality calculations."""
    reviewer = TradeReviewer()
    
    # Price difference > 1% -> Poor entry quality
    res = reviewer.review_trade(trade_id="t1", slippage_ms=250.0, entry_price=100.0, filled_price=101.5)
    assert res.entry_quality == "POOR"
    assert any("limit orders" in s.action for s in res.suggestions)
    assert any("Route to alternative exchange" in s.action for s in res.suggestions)


def test_portfolio_reviews():
    """Verify concentration threshold checks."""
    reviewer = PortfolioReviewer()
    weights = {"BTC": 0.5, "ETH": 0.5}  # Concentration exceeds 40%

    res = reviewer.review_portfolio(portfolio_id="p1", weights=weights)
    assert res.diversification_score == 0.5
    assert len(res.suggestions) == 1


def test_risk_reviews():
    """Verify risk reviews evaluate VaR and leverage statuses."""
    reviewer = RiskReviewer()

    res = reviewer.review_risk(var_utilization=0.85, leverage=1.8)
    assert res.leverage_status == "HIGH"
    assert len(res.suggestions) == 2


def test_explanation_generations():
    """Verify natural-language metric narratives constructions."""
    engine = ExplanationEngine()
    res = engine.explain_metric_event(metric="drawdown", value=0.18, rationale="High volatility spike")
    assert "drawdown" in res.narrative
    assert "0.18" in res.narrative


def test_report_compilation():
    """Verify daily reports summaries compilation."""
    generator = ReportGenerator()
    insights = [Insight(title="MVO balance", description="Diversification optimized")]
    warnings = []

    report = generator.compile_daily_report(summary="Session OK", insights=insights, warnings=warnings)
    assert report.summary == "Session OK"
    assert len(report.insights) == 1


def test_trading_journals():
    """Verify trading journal observations entries log."""
    journal = TradingJournal()
    entry = journal.create_journal_entry(trades_count=12, observations="System stabilized")
    assert entry.trades_reviewed_count == 12
    assert "stabilized" in entry.observations


def test_ai_orchestrator(orchestrator):
    """Verify orchestrator coordinates validations and persists log history."""
    # Text gen
    res = orchestrator.generate_advisory_response(prompt="Evaluate market beta")
    assert "Advisory" in res.text

    # Review
    orchestrator.run_strategy_review(strategy_id="strat_999", sharpe=2.0, sortino=2.2, drawdown=0.08)
    assert orchestrator.repository.get_strategy_review("strat_999") is not None
