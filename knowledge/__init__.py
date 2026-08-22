"""TOJI Quantitative Knowledge Engine package.

Exposes canonical models, Belief conflict engine, IF/THEN Rule engine,
Evidence lineage engines, Knowledge Graph traversals, Contradiction detectors,
Confidence scoring calculator, Proof Reasoning trace generators, and reports generators.
"""

__version__ = "0.1.0"
__package_name__ = "toji-knowledge"

from knowledge.models import (
    KnowledgeStatus,
    SourceReference,
    Evidence,
    Rule,
    Belief,
    Insight,
    Relationship,
    KnowledgeEntry,
)
from knowledge.evidence.engine import EvidenceEngine
from knowledge.beliefs.engine import BeliefEngine
from knowledge.rules.engine import RuleEngine
from knowledge.graph.manager import KnowledgeGraph
from knowledge.contradictions.detector import ContradictionEngine, InvestigationTask
from knowledge.confidence.calculator import ConfidenceCalculator
from knowledge.reasoning.engine import ReasoningEngine
from knowledge.reports.generator import KnowledgeReportGenerator

__all__ = [
    "KnowledgeStatus",
    "SourceReference",
    "Evidence",
    "Rule",
    "Belief",
    "Insight",
    "Relationship",
    "KnowledgeEntry",
    "EvidenceEngine",
    "BeliefEngine",
    "RuleEngine",
    "KnowledgeGraph",
    "ContradictionEngine",
    "InvestigationTask",
    "ConfidenceCalculator",
    "ReasoningEngine",
    "KnowledgeReportGenerator",
]
