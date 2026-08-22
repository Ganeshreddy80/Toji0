"""Event contracts for the AI Quant Intelligence Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class AIAnalysisStarted(BaseEvent):
    """Fired when prompt generation begins."""
    pass


@dataclass(frozen=True)
class AIAnalysisCompleted(BaseEvent):
    """Fired when LLM output text is received."""
    pass


@dataclass(frozen=True)
class RecommendationGenerated(BaseEvent):
    """Fired when optimization recommendation is logged."""
    pass


@dataclass(frozen=True)
class TradeReviewed(BaseEvent):
    """Fired when trade execution entries are reviewed."""
    pass


@dataclass(frozen=True)
class StrategyReviewed(BaseEvent):
    """Fired when strategy ratios Sortino win rates are audited."""
    pass


@dataclass(frozen=True)
class RiskReviewed(BaseEvent):
    """Fired when VaR limits or leverage statuses are reviewed."""
    pass


@dataclass(frozen=True)
class PortfolioReviewed(BaseEvent):
    """Fired when weights allocations or sector counts are reviewed."""
    pass


@dataclass(frozen=True)
class ReportGenerated(BaseEvent):
    """Fired when Daily or Weekly summary PDFs compile."""
    pass


@dataclass(frozen=True)
class JournalUpdated(BaseEvent):
    """Fired when session observations journal diary is saved."""
    pass
