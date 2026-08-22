"""Abstract contracts for the Knowledge Graph Engine.
"""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Any, Dict, List, Optional

from research_platform.knowledge_graph.models import (
    GraphSnapshot,
    KnowledgeEdge,
    KnowledgeNode,
    TraversalResult
)


class IKnowledgeGraphRepository(abc.ABC):
    """Abstract contract for logging nodes and edges."""

    @abc.abstractmethod
    def save_node(self, node: KnowledgeNode) -> None:
        """Persist node and update versions cache."""

    @abc.abstractmethod
    def save_edge(self, edge: KnowledgeEdge) -> None:
        """Persist edge connection."""

    @abc.abstractmethod
    def get_graph_at_timestamp(self, ts: datetime) -> GraphSnapshot:
        """Query elements active before timestamp."""


class IQueryEngine(abc.ABC):
    """Abstract contract for queries filters."""

    @abc.abstractmethod
    def find_nodes_by_type(self, node_type: str) -> List[KnowledgeNode]:
        """Query matching nodes list."""


class IGraphTraversalEngine(abc.ABC):
    """Abstract contract for multi-hop BFS paths traversals."""

    @abc.abstractmethod
    def traverse_path(self, start_node_id: str, target_node_id: str) -> TraversalResult:
        """Execute BFS paths query."""
class IKnowledgeGraphOrchestrator(abc.ABC):
    """Abstract contract for knowledge graph orchestrator."""
    pass
