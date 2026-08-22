"""TOJI Decision Engine.

Provides deterministic institutional decision logic aggregating Research,
Analytics, Risk, Portfolio, and Knowledge committees into explainable,
auditable investment recommendations.
"""

from __future__ import annotations

__version__ = "0.1.0"
__package_name__ = "toji-decision"

from decision.models import (
    CommitteeVote,
    DecisionState,
    InvestmentDecision,
    JournalEntry,
    TimelineEvent,
    TimelineState,
)
from decision.committees.base import BaseCommittee
from decision.committees.research import ResearchCommittee
from decision.committees.risk import RiskCommittee
from decision.committees.portfolio import PortfolioCommittee
from decision.committees.timing import TimingCommittee
from decision.committees.knowledge import KnowledgeCommittee
from decision.voting.engine import InvestmentCommittee
from decision.explainability.engine import ExplainabilityEngine
from decision.journal.manager import DecisionJournal
from decision.reports.generator import DecisionReportGenerator

__all__ = [
    "CommitteeVote",
    "DecisionState",
    "InvestmentDecision",
    "JournalEntry",
    "TimelineEvent",
    "TimelineState",
    "BaseCommittee",
    "ResearchCommittee",
    "RiskCommittee",
    "PortfolioCommittee",
    "TimingCommittee",
    "KnowledgeCommittee",
    "InvestmentCommittee",
    "ExplainabilityEngine",
    "DecisionJournal",
    "DecisionReportGenerator",
]
