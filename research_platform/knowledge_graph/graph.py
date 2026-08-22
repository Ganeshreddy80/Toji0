"""Graph representation map list trackers.
"""

from __future__ import annotations

from typing import Dict, List

from research_platform.knowledge_graph.models import KnowledgeEdge, KnowledgeNode


class Graph:
    """Graph structure containing entities and connections."""

    def __init__(self) -> None:
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.edges: Dict[str, KnowledgeEdge] = {}
        self.adjacency: Dict[str, List[str]] = {}

    def add_node(self, node: KnowledgeNode) -> None:
        self.nodes[node.node_id] = node
        if node.node_id not in self.adjacency:
            self.adjacency[node.node_id] = []

    def add_edge(self, edge: KnowledgeEdge) -> None:
        self.edges[edge.edge_id] = edge
        if edge.source_id in self.adjacency:
            self.adjacency[edge.source_id].append(edge.target_id)
