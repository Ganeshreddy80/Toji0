"""Knowledge Graph manager for linking quantitative ontology nodes and traversing relationships."""

from __future__ import annotations

from collections import deque
from typing import Any
from knowledge.models import Relationship


class KnowledgeGraph:
    """Stores nodes and relational edges, and executes graph search traversals."""

    def __init__(self) -> None:
        # Maps node_id -> {"node_type": str, "properties": dict}
        self._nodes: dict[str, dict[str, Any]] = {}
        # Maps source_id -> list of Relationship edges starting from it
        self._adjacency: dict[str, list[Relationship]] = {}

    def add_node(self, node_id: str, node_type: str, properties: dict[str, Any] | None = None) -> None:
        """Add or update a node in the graph."""
        self._nodes[node_id] = {
            "node_type": node_type,
            "properties": properties or {}
        }
        if node_id not in self._adjacency:
            self._adjacency[node_id] = []

    def add_edge(self, source_id: str, target_id: str, rel_type: str) -> Relationship:
        """Insert a directed edge representing a relationship between two existing nodes."""
        if source_id not in self._nodes or target_id not in self._nodes:
            raise KeyError("Both source and target nodes must exist in the graph.")
            
        edge = Relationship(
            source_id=source_id,
            target_id=target_id,
            rel_type=rel_type
        )
        # Store in adjacency list
        self._adjacency[source_id].append(edge)
        return edge

    def get_neighbors(self, node_id: str, rel_type: str | None = None) -> list[tuple[str, str]]:
        """Retrieve neighboring node IDs connected from this node.
        
        Returns:
            list of (target_id, relationship_type)
        """
        if node_id not in self._adjacency:
            return []
            
        edges = self._adjacency[node_id]
        if rel_type is not None:
            edges = [e for e in edges if e.rel_type == rel_type]
            
        return [(e.target_id, e.rel_type) for e in edges]

    def find_path(self, start_id: str, end_id: str) -> list[str] | None:
        """Find the shortest path of node IDs from start_id to end_id using Breadth-First Search (BFS).
        
        Returns:
            list of node IDs forming the path, or None if no path exists.
        """
        if start_id not in self._nodes or end_id not in self._nodes:
            return None
            
        if start_id == end_id:
            return [start_id]
            
        # BFS queue stores (current_node, path_taken_list)
        queue: deque[tuple[str, list[str]]] = deque([(start_id, [start_id])])
        visited: set[str] = {start_id}
        
        while queue:
            curr, path = queue.popleft()
            
            for neighbor_id, _ in self.get_neighbors(curr):
                if neighbor_id == end_id:
                    return path + [neighbor_id]
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, path + [neighbor_id]))
                    
        return None

    def list_nodes_by_type(self, node_type: str) -> list[str]:
        """Query all node IDs matching a specific category/type."""
        return [n_id for n_id, data in self._nodes.items() if data["node_type"] == node_type]

    def get_node_data(self, node_id: str) -> dict[str, Any] | None:
        """Retrieve the type and properties mapping of a node."""
        return self._nodes.get(node_id)
