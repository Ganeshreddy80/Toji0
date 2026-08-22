"""Knowledge Graph Orchestrator coordinating node registrations, edge links, traversals and similarity searches.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.knowledge_graph.causality import CausalityEngine
from research_platform.knowledge_graph.dependency import DependencyEngine
from research_platform.knowledge_graph.edge import EdgeEngine
from research_platform.knowledge_graph.entity import EntityMapper
from research_platform.knowledge_graph.events import (
    EdgeRegistered,
    GraphSnapshotCreated,
    NodeRegistered,
    TraversalExecuted
)
from research_platform.knowledge_graph.graph_search import GraphSearchEngine
from research_platform.knowledge_graph.graph_traversal import GraphTraversalEngine
from research_platform.knowledge_graph.interfaces import IKnowledgeGraphOrchestrator
from research_platform.knowledge_graph.lineage import LineageEngine
from research_platform.knowledge_graph.models import (
    DependencyResult,
    GraphSnapshot,
    KnowledgeEdge,
    KnowledgeNode,
    LineageResult,
    Relationship,
    RootCauseResult,
    SimilarityResult,
    TimelineResult,
    TraversalResult

)
from research_platform.knowledge_graph.node import NodeEngine
from research_platform.knowledge_graph.query_engine import QueryEngine
from research_platform.knowledge_graph.relationship import RelationshipValidator
from research_platform.knowledge_graph.repository import KnowledgeGraphRepository
from research_platform.knowledge_graph.similarity import SimilarityEngine
from research_platform.knowledge_graph.timeline import TimelineEngine
from research_platform.knowledge_graph.visualization import GraphVisualizer

logger = logging.getLogger(__name__)


class KnowledgeGraphOrchestrator(IKnowledgeGraphOrchestrator):
    """Semantic graph coordinator managing cycle detections and multi-hop paths traversal."""

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._repo = KnowledgeGraphRepository()

        # Engines
        self._query_engine = QueryEngine(self._repo)
        self._traversal_engine = GraphTraversalEngine(self._repo)
        self._similarity_engine = SimilarityEngine()
        self._dependency_engine = DependencyEngine(self._repo)
        self._lineage_engine = LineageEngine(self._repo)
        self._causality_engine = CausalityEngine(self._repo)
        self._timeline_engine = TimelineEngine(self._repo)
        self._visualizer = GraphVisualizer(self._repo)
        self._search_engine = GraphSearchEngine(self._repo)

    @property
    def repository(self) -> KnowledgeGraphRepository:
        return self._repo

    def register_node(
        self,
        node_id: str,
        node_type: str,
        subsystem: str,
        event: str,
        author: str,
        properties: Dict[str, Any] = None
    ) -> KnowledgeNode:
        """Create new entity node in graph and persist."""
        node = NodeEngine.create_node(node_id, node_type, subsystem, event, author, properties)
        self._repo.save_node(node)
        
        self._event_bus.publish(NodeRegistered(payload={"node_id": node_id, "node_type": node_type}))
        return node

    def link_nodes(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        subsystem: str,
        properties: Dict[str, Any] = None
    ) -> Optional[KnowledgeEdge]:
        """Validate linkage rules constraints and create directed edge."""
        # Find nodes in repository
        nodes = {n.node_id: n for n in self._repo.list_nodes()}
        source = nodes.get(source_id)
        target = nodes.get(target_id)
        
        if not source or not target:
            logger.warning("Link failed: Node source or target does not exist.")
            return None

        # Validate constraint rules
        if not RelationshipValidator.validate_link(source, target, relationship_type):
            logger.warning("Link failed: Relationship type constraint violation.")
            return None

        edge = EdgeEngine.create_edge(source_id, target_id, relationship_type, subsystem, properties)
        self._repo.save_edge(edge)
        
        self._event_bus.publish(EdgeRegistered(payload={"edge_id": edge.edge_id, "type": relationship_type}))
        return edge

    def traverse_graph_path(self, start_id: str, target_id: str) -> TraversalResult:
        """Query multi-hop traversal paths."""
        res = self._traversal_engine.traverse_path(start_id, target_id)
        self._event_bus.publish(TraversalExecuted(payload={"start_id": start_id, "target_id": target_id}))
        return res

    def resolve_dependencies(self) -> DependencyResult:
        return self._dependency_engine.resolve_dependencies()

    def trace_lineage(self, target_id: str) -> LineageResult:
        return self._lineage_engine.trace_lineage(target_id)

    def analyze_drawdown_cause(self, drawdown_node_id: str) -> RootCauseResult:
        return self._causality_engine.analyze_root_cause(drawdown_node_id)

    def compile_chronological_timeline(self) -> List[TimelineResult]:
        return self._timeline_engine.compile_timeline()

    def get_visual_schema(self) -> str:
        return self._visualizer.render_mermaid()

    def search_by_properties(self, keyword: str) -> List[KnowledgeNode]:
        return self._search_engine.search_by_keyword(keyword)
