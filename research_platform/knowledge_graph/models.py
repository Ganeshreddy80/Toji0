"""Immutable Pydantic models for the Knowledge Graph Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class NodeMetadata(BaseModel):
    """Lineage tracking metadata for KnowledgeNodes."""

    subsystem: str
    originating_event: str
    author: str  # human or AI
    confidence_score: float = 1.0

    model_config = ConfigDict(frozen=True)


class KnowledgeNode(BaseModel):
    """Representation of a singular graph entity node."""

    node_id: str
    node_type: str  # RESEARCH, STRATEGY, TRADE, etc.
    version: int = 1
    properties: Dict[str, Any] = Field(default_factory=dict)
    metadata: NodeMetadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class EdgeMetadata(BaseModel):
    """Lineage tracking metadata for KnowledgeEdges."""

    subsystem: str
    confidence_score: float = 1.0

    model_config = ConfigDict(frozen=True)


class KnowledgeEdge(BaseModel):
    """Directed connection edge linking nodes."""

    edge_id: str
    source_id: str
    target_id: str
    relationship_type: str  # depends_on, derived_from, approved_by, etc.
    version: int = 1
    properties: Dict[str, Any] = Field(default_factory=dict)
    metadata: EdgeMetadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class Relationship(BaseModel):
    """Advisory relationship wrapper mapping nodes."""

    source_node: KnowledgeNode
    target_node: KnowledgeNode
    relationship_type: str

    model_config = ConfigDict(frozen=True)


class Entity(BaseModel):
    """Core domain entity wrapped in graph node details."""

    entity_id: str
    node_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class GraphSnapshot(BaseModel):
    """Reconstructed nodes and edges snapshot at target timestamp."""

    snapshot_timestamp: datetime
    nodes: List[KnowledgeNode] = Field(default_factory=list)
    edges: List[KnowledgeEdge] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class GraphVersion(BaseModel):
    """Graph version tracker."""

    version_id: int
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class TraversalResult(BaseModel):
    """Multi-hop search outputs path."""

    visited_node_ids: List[str] = Field(default_factory=list)
    edges_traversed: List[KnowledgeEdge] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class DependencyResult(BaseModel):
    """Dependency resolver ordering output."""

    ordered_node_ids: List[str] = Field(default_factory=list)
    cycles_detected: bool = False

    model_config = ConfigDict(frozen=True)


class SimilarityResult(BaseModel):
    """Regime similarity score comparison."""

    source_node_id: str
    match_node_id: str
    similarity_score: float

    model_config = ConfigDict(frozen=True)


class TimelineResult(BaseModel):
    """Chronologically sorted logs details."""

    event_name: str
    timestamp: datetime
    properties: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class RootCauseResult(BaseModel):
    """Drawdown root cause diagnosis results."""

    target_node_id: str
    culprit_node_id: str
    explanation: str
    confidence: float

    model_config = ConfigDict(frozen=True)


class LineageResult(BaseModel):
    """Source-to-target mapping lineage trail."""

    source_ids: List[str] = Field(default_factory=list)
    target_id: str

    model_config = ConfigDict(frozen=True)


class EvidenceReference(BaseModel):
    """Advisory lessons backup reference."""

    evidence_id: str
    metric_name: str
    metric_value: float

    model_config = ConfigDict(frozen=True)


class NodeVersion(BaseModel):
    """Single node version metadata container."""

    node_id: str
    version: int
    properties: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class EdgeVersion(BaseModel):
    """Single edge version metadata container."""

    edge_id: str
    version: int
    properties: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)
