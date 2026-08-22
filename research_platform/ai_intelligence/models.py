"""Immutable Pydantic models for the AI Quant Intelligence Engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AIRequest(BaseModel):
    """Payload prompt request for the LLM."""

    prompt: str
    system_instruction: Optional[str] = None
    temperature: float = 0.2

    model_config = ConfigDict(frozen=True)


class AIResponse(BaseModel):
    """Raw response output from the LLM."""

    text: str
    confidence_score: float = 1.0
    reasoning_chain: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class Insight(BaseModel):
    """Single diagnostic insight."""

    title: str
    description: str

    model_config = ConfigDict(frozen=True)


class Warning(BaseModel):
    """Active boundary warning."""

    severity: str
    message: str

    model_config = ConfigDict(frozen=True)


class ImprovementSuggestion(BaseModel):
    """Sizing or execution suggestion."""

    action: str
    rationale: str

    model_config = ConfigDict(frozen=True)


class StrategyReview(BaseModel):
    """Detailed strategy metrics review."""

    strategy_id: str
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    suggestions: List[ImprovementSuggestion] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class TradeReview(BaseModel):
    """Completed trade evaluation."""

    trade_id: str
    entry_quality: str
    exit_quality: str
    slippage_ms: float
    suggestions: List[ImprovementSuggestion] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class PortfolioReview(BaseModel):
    """Aggregate weights allocations review."""

    portfolio_id: str
    diversification_score: float
    suggestions: List[ImprovementSuggestion] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class RiskReview(BaseModel):
    """VaR budgets limit limits compliance review."""

    var_utilization: float
    leverage_status: str
    suggestions: List[ImprovementSuggestion] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class Recommendation(BaseModel):
    """Advisory decision recommendations."""

    recommendation_id: str
    actionable_step: str
    reasoning: str
    confidence: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class DailyReport(BaseModel):
    """Daily operational summary report."""

    report_id: str
    summary: str
    insights: List[Insight] = Field(default_factory=list)
    warnings: List[Warning] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class WeeklyReport(BaseModel):
    """Weekly operational summary report."""

    report_id: str
    summary: str
    insights: List[Insight] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class JournalEntry(BaseModel):
    """Lessons learned journal entry logs."""

    entry_id: str
    trades_reviewed_count: int
    observations: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class Explanation(BaseModel):
    """Natural-language explanation for events."""

    explanation_id: str
    metric_referenced: str
    narrative: str

    model_config = ConfigDict(frozen=True)


class ConfidenceScore(BaseModel):
    """Confidence value container."""

    score: float

    model_config = ConfigDict(frozen=True)


class MarketContext(BaseModel):
    """State snapshot context."""

    regime_type: str  # TRENDING, SIDEWAYS, VOLATILE
    volatility_score: float

    model_config = ConfigDict(frozen=True)


class PerformanceSummary(BaseModel):
    """Equity curve diagnostics values."""

    cagr: float
    sharpe: float
    sortino: float

    model_config = ConfigDict(frozen=True)


class ReasoningChain(BaseModel):
    """Diagnostic steps logs."""

    steps: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)
