"""Feature Lineage tracker implementation.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Set

from research_platform.feature_platform.interfaces import ILineageTracer
from research_platform.feature_platform.models import LineageNode


class LineageTracer(ILineageTracer):
    """Tracks dependency relations and computes lineage paths backward."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._nodes: Dict[str, LineageNode] = {}

    def register_node(self, node: LineageNode) -> None:
        """Register a node in the lineage trace map."""
        with self._lock:
            self._nodes[node.node_id] = node

    def get_lineage(self, node_id: str) -> List[LineageNode]:
        """Trace lineage path backward from node_id to root sources."""
        with self._lock:
            if node_id not in self._nodes:
                return []

            path = []
            visited = set()
            stack = [node_id]

            while stack:
                curr = stack.pop()
                if curr in visited:
                    continue
                visited.add(curr)
                node = self._nodes.get(curr)
                if node:
                    path.append(node)
                    stack.extend(node.parents)

            return path
