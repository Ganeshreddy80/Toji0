"""Query Engine filtering nodes and edges based on type attributes.
"""

from __future__ import annotations

from typing import List

from research_platform.knowledge_graph.interfaces import IQueryEngine
from research_platform.knowledge_graph.models import KnowledgeEdge, KnowledgeNode


class QueryEngine(IQueryEngine):
    """Executes structured filters lookups against repository logs."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def find_nodes_by_type(self, node_type: str) -> List[KnowledgeNode]:
        """Query matching nodes list."""
        nodes = self.repository.list_nodes()
        return [n for n in nodes if n.node_type == node_type.upper()]

    def find_edges_by_relationship(self, relationship_type: str) -> List[KnowledgeEdge]:
        edges = self.repository.list_edges()
        return [e for e in edges if e.relationship_type == relationship_type.lower()]
