"""Feature Provenance Graph module.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Set

from research_platform.feature_platform.models import LineageNode


class FeatureProvenanceGraph:
    """Manages tracking lineage nodes and performing graph query traversals."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._nodes: Dict[str, LineageNode] = {}

    def register_node(self, node: LineageNode) -> None:
        """Register a node in the lineage trace map."""
        with self._lock:
            self._nodes[node.node_id] = node

    def trace_backward(self, node_id: str) -> List[str]:
        """Find all upstream parent dependencies recursively."""
        with self._lock:
            if node_id not in self._nodes:
                return []

            visited = set()
            stack = [node_id]

            while stack:
                curr = stack.pop()
                if curr in visited:
                    continue
                visited.add(curr)
                node = self._nodes.get(curr)
                if node:
                    stack.extend(node.parents)

            visited.remove(node_id)
            return list(visited)

    def trace_forward(self, node_id: str) -> List[str]:
        """Find all downstream children dependencies recursively (Impact Analysis)."""
        with self._lock:
            visited = set()
            stack = [node_id]

            while stack:
                curr = stack.pop()
                if curr in visited:
                    continue
                visited.add(curr)
                # Find children (any node that has curr as a parent)
                for node in self._nodes.values():
                    if curr in node.parents:
                        stack.append(node.node_id)

            visited.remove(node_id)
            return list(visited)
