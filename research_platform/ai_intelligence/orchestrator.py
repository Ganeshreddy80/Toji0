"""AI Intelligence Orchestrator coordinating contexts gathering, LLM prompts, and reviews persistence.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.ai_intelligence.context import AIContextBuilder
from research_platform.ai_intelligence.events import (
    AIAnalysisCompleted,
    AIAnalysisStarted,
    RecommendationGenerated,
    StrategyReviewed,
    TradeReviewed
)
from research_platform.ai_intelligence.explanation import ExplanationEngine
from research_platform.ai_intelligence.journal import TradingJournal
from research_platform.ai_intelligence.memory import AIMemory
from research_platform.ai_intelligence.models import (
    AIRequest,
    AIResponse,
    DailyReport,
    JournalEntry,
    Recommendation,
    StrategyReview,
    TradeReview
)
from research_platform.ai_intelligence.performance_analyzer import PerformanceAnalyzer
from research_platform.ai_intelligence.portfolio_reviewer import PortfolioReviewer
from research_platform.ai_intelligence.prompt_builder import PromptBuilder
from research_platform.ai_intelligence.provider import MockLLMProvider
from research_platform.ai_intelligence.recommendation import RecommendationEngine
from research_platform.ai_intelligence.regime_reasoner import MarketRegimeReasoner
from research_platform.ai_intelligence.report_generator import ReportGenerator
from research_platform.ai_intelligence.repository import AIIntelligenceRepository
from research_platform.ai_intelligence.risk_reviewer import RiskReviewer
from research_platform.ai_intelligence.strategy_reviewer import StrategyReviewer
from research_platform.ai_intelligence.trade_reviewer import TradeReviewer

logger = logging.getLogger(__name__)


class AIIntelligenceOrchestrator:
    """Manages AI decision-support loops, generating strategy reviews and reports."""

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._repo = AIIntelligenceRepository()
        
        # Engines
        self._provider = MockLLMProvider()
        self._context_builder = AIContextBuilder()
        self._memory = AIMemory()
        self._prompt_builder = PromptBuilder()

        # Reviewers
        self._strategy_reviewer = StrategyReviewer()
        self._trade_reviewer = TradeReviewer()
        self._portfolio_reviewer = PortfolioReviewer()
        self._risk_reviewer = RiskReviewer()
        self._performance_analyzer = PerformanceAnalyzer()
        self._regime_reasoner = MarketRegimeReasoner()
        self._recommendation = RecommendationEngine()
        self._explanation = ExplanationEngine()
        self._report_generator = ReportGenerator()
        self._journal = TradingJournal()

    @property
    def repository(self) -> AIIntelligenceRepository:
        return self._repo

    def generate_advisory_response(self, prompt: str) -> AIResponse:
        """Call LLM provider for generic investment queries or insights requests."""
        self._event_bus.publish(AIAnalysisStarted(payload={"prompt": prompt}))

        req = AIRequest(prompt=prompt)
        res = self._provider.generate_text(req)

        self._event_bus.publish(AIAnalysisCompleted(payload={"response": res.text}))
        return res

    def run_strategy_review(
        self,
        strategy_id: str,
        sharpe: float,
        sortino: float,
        drawdown: float
    ) -> StrategyReview:
        """Evaluate strategy returns parameters and save diagnostics profile."""
        review = self._strategy_reviewer.review_strategy(strategy_id, sharpe, sortino, drawdown)
        self._repo.save_strategy_review(review)
        self._event_bus.publish(StrategyReviewed(payload={"strategy_id": strategy_id}))
        return review

    def run_trade_review(
        self,
        trade_id: str,
        slippage_ms: float,
        entry_price: float,
        filled_price: float
    ) -> TradeReview:
        """Evaluate completed trade execution parameters."""
        review = self._trade_reviewer.review_trade(trade_id, slippage_ms, entry_price, filled_price)
        self._repo.save_trade_review(review)
        self._event_bus.publish(TradeReviewed(payload={"trade_id": trade_id}))
        return review

    def generate_action_recommendation(
        self,
        action: str,
        reasoning: str,
        confidence: float
    ) -> Recommendation:
        """Create advisory recommendation action and notify Event Bus."""
        rec = self._recommendation.generate_recommendation(action, reasoning, confidence)
        self._repo.save_recommendation(rec)
        self._event_bus.publish(RecommendationGenerated(payload={"recommendation_id": rec.recommendation_id}))
        return rec
