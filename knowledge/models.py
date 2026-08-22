"""Canonical Pydantic models for versioned quantitative knowledge, rules, and beliefs."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class KnowledgeStatus(enum.Enum):
    """Lifecycle status states for rules and belief nodes."""

    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"
    CONFLICTED = "conflicted"


class SourceReference(BaseModel):
    """Traceable citation to research, backtesting, or statistical runs."""

    ref_type: str = Field(..., description="Source type: e.g. 'experiment', 'paper', 'backtest'")
    ref_id: str = Field(..., description="ID of source run or artifact")
    description: str = Field(..., description="Qualitative context or parameter summary")

    model_config = {"frozen": True}


class Evidence(BaseModel):
    """Factual proof item backed by mathematical outcomes and statistics."""

    evidence_id: str = Field(...)
    source: SourceReference = Field(...)
    metric_name: str = Field(..., description="Evaluated statistic (e.g. 'sharpe', 't_stat')")
    metric_value: float = Field(...)
    sample_size: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class Rule(BaseModel):
    """A deterministic, logic-based directive (IF/THEN expression) derived from research."""

    rule_id: str = Field(...)
    name: str = Field(...)
    rule_type: str = Field(..., description="Category: e.g. 'regime', 'risk', 'portfolio', 'research'")
    expression: str = Field(..., description="IF/THEN conditional and action representation")
    confidence_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list, description="Associated evidence IDs backing the rule")
    status: KnowledgeStatus = Field(default=KnowledgeStatus.ACTIVE)

    model_config = {"frozen": True}


class Belief(BaseModel):
    """A claim or quantitative thesis held by the platform, updated by evidence."""

    belief_id: str = Field(...)
    claim: str = Field(..., description="The theoretical assertation (e.g. 'BTC exhibits trend momentum')")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    is_retired: bool = Field(default=False)
    conflicting_belief_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class Insight(BaseModel):
    """Aggregated structural context generated from active beliefs and strategy rules."""

    insight_id: str = Field(...)
    summary: str = Field(...)
    description: str = Field(...)
    derived_rules: list[str] = Field(default_factory=list)
    derived_beliefs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class Relationship(BaseModel):
    """Directed connection between ontology nodes in the Knowledge Graph."""

    source_id: str = Field(...)
    target_id: str = Field(...)
    rel_type: str = Field(..., description="Relation link: e.g. 'supports', 'contradicts', 'derived_from'")

    model_config = {"frozen": True}


class KnowledgeEntry(BaseModel):
    """Wrapper entry representing versioned elements indexed in the Knowledge Engine."""

    entry_id: str = Field(...)
    name: str = Field(...)
    version: str = Field(default="1.0.0")
    status: KnowledgeStatus = Field(default=KnowledgeStatus.ACTIVE)
    content_type: str = Field(..., description="Type of wrapped node: 'rule', 'belief', 'insight'")
    content_id: str = Field(..., description="Reference to wrapped content ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}
