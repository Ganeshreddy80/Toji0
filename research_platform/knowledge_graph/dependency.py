"""Dependency Engine resolving upstream/downstream connection chains.
"""

from __future__ import annotations

from typing import Dict, List, Set

from research_platform.knowledge_graph.models import DependencyResult


class DependencyEngine:
    """Sorts nodes topologically based on depends_on connection links."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def resolve_dependencies(self) -> DependencyResult:
        """Topological sort resolver identifying cyclic packages loops."""
        nodes = self.repository.list_nodes()
        edges = self.repository.list_edges()

        # Build adjacency for depends_on
        adj: Dict[str, Set[str]] = {n.node_id: set() for n in nodes}
        in_degree: Dict[str, int] = {n.node_id: 0 for n in nodes}

        for e in edges:
            if e.relationship_type == "depends_on":
                # e.source_id depends on e.target_id -> target_id should compile first
                # target -> source link
                u = e.target_id
                v = e.source_id
                if u in adj and v in adj:
                    if v not in adj[u]:
                        adj[u].add(v)
                        in_degree[v] += 1

        # Queue of nodes with in_degree == 0
        queue = [n_id for n_id, deg in in_degree.items() if deg == 0]
        ordered = []

        while queue:
            curr = queue.pop(0)
            ordered.append(curr)
            
            for neighbor in adj.get(curr, set()):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        has_cycle = len(ordered) != len(nodes)
        return DependencyResult(
            ordered_node_ids=ordered,
            cycles_detected=has_cycle
        )
