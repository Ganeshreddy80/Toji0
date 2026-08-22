"""Lineage Engine tracing dataset sources and indicators connections.
"""

from __future__ import annotations

from typing import List, Set

from research_platform.knowledge_graph.models import LineageResult


class LineageEngine:
    """Traces parent sources using derived_from relationship links."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def trace_lineage(self, target_node_id: str) -> LineageResult:
        """Collects ancestor nodes contributing to target dataset/feature."""
        edges = self.repository.list_edges()
        
        # Build derived_from mapping child -> parents
        parent_map = {}
        for e in edges:
            if e.relationship_type == "derived_from":
                child = e.source_id
                parent = e.target_id
                if child not in parent_map:
                    parent_map[child] = []
                parent_map[child].append(parent)

        sources: Set[str] = set()
        queue = [target_node_id]
        
        while queue:
            curr = queue.pop(0)
            parents = parent_map.get(curr, [])
            for p in parents:
                if p not in sources:
                    sources.add(p)
                    queue.append(p)

        return LineageResult(
            source_ids=list(sources),
            target_id=target_node_id
        )
