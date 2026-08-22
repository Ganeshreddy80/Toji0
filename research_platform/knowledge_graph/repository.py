"""Database repository holding append-only versioned nodes and edges.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List

from research_platform.knowledge_graph.interfaces import IKnowledgeGraphRepository
from research_platform.knowledge_graph.models import GraphSnapshot, KnowledgeEdge, KnowledgeNode


class KnowledgeGraphRepository(IKnowledgeGraphRepository):
    """Memory database repository for TOJI semantic knowledge graphs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._nodes: Dict[str, List[KnowledgeNode]] = {}
        self._edges: Dict[str, List[KnowledgeEdge]] = {}

    def save_node(self, node: KnowledgeNode) -> None:
        """Persist node and update versions cache."""
        with self._lock:
            if node.node_id not in self._nodes:
                self._nodes[node.node_id] = []
            self._nodes[node.node_id].append(node)

    def save_edge(self, edge: KnowledgeEdge) -> None:
        """Persist edge connection."""
        with self._lock:
            if edge.edge_id not in self._edges:
                self._edges[edge.edge_id] = []
            self._edges[edge.edge_id].append(edge)

    def get_graph_at_timestamp(self, ts: datetime) -> GraphSnapshot:
        """Query elements active before timestamp."""
        with self._lock:
            filtered_nodes = []
            filtered_edges = []
            
            # Select latest version before ts for each node
            for node_history in self._nodes.values():
                valid = [n for n in node_history if n.created_at <= ts]
                if valid:
                    # Pick max version
                    filtered_nodes.append(max(valid, key=lambda x: x.version))

            # Select latest version before ts for each edge
            for edge_history in self._edges.values():
                valid = [e for e in edge_history if e.created_at <= ts]
                if valid:
                    filtered_edges.append(max(valid, key=lambda x: x.version))

            return GraphSnapshot(
                snapshot_timestamp=ts,
                nodes=filtered_nodes,
                edges=filtered_edges
            )

    def list_nodes(self) -> List[KnowledgeNode]:
        with self._lock:
            # Flatten to current latest version
            return [max(nodes, key=lambda x: x.version) for nodes in self._nodes.values() if nodes]

    def list_edges(self) -> List[KnowledgeEdge]:
        with self._lock:
            return [max(edges, key=lambda x: x.version) for edges in self._edges.values() if edges]
class KnowledgeGraphOrchestrator:
    """Orchestrates query engines and traversals."""
    pass
