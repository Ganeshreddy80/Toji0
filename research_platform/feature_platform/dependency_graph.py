"""Dependency Graph engine for topological sorting, cycle detection, and impact analysis.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Set


class DependencyGraph:
    """Manages feature dependencies, detects loops, and determines execution orders."""

    def __init__(self) -> None:
        self._graph: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_graph: Dict[str, Set[str]] = defaultdict(set)

    def add_node(self, name: str, dependencies: List[str]) -> None:
        """Add a node and its dependency links to the graph."""
        self._graph[name] = set(dependencies)
        for dep in dependencies:
            self._reverse_graph[dep].add(name)

    def remove_node(self, name: str) -> None:
        """Remove a node from the graph."""
        self._graph.pop(name, None)
        self._reverse_graph.pop(name, None)
        for deps in self._graph.values():
            deps.discard(name)
        for revs in self._reverse_graph.values():
            revs.discard(name)

    def has_cycle(self) -> bool:
        """Check if the graph contains any circular reference loops."""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in self._graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for node in list(self._graph.keys()):
            if node not in visited:
                if dfs(node):
                    return True
        return False

    def topological_sort(self, target_nodes: List[str] = None) -> List[str]:
        """Perform a topological sort, determining execution order.

        Args:
            target_nodes: Sub-list of target feature nodes to calculate.
                          If None, sorts the entire graph.

        Returns:
            List of node names in execution order (dependencies first).
        """
        if self.has_cycle():
            raise ValueError("Circular dependency detected in feature graph.")

        # Compute dependencies subset if specific targets requested
        nodes_to_resolve = set(self._graph.keys())
        if target_nodes is not None:
            nodes_to_resolve = set()
            queue = deque(target_nodes)
            while queue:
                current = queue.popleft()
                if current not in nodes_to_resolve:
                    nodes_to_resolve.add(current)
                    for dep in self._graph.get(current, []):
                        queue.append(dep)

        # Kahn's algorithm for topological sorting
        in_degree = {node: 0 for node in nodes_to_resolve}
        for node in nodes_to_resolve:
            for dep in self._graph.get(node, []):
                if dep in in_degree:
                    in_degree[node] += 1

        # Queue nodes with no dependencies (in-degree == 0)
        queue = deque([n for n, d in in_degree.items() if d == 0])
        order = []

        while queue:
            node = queue.popleft()
            order.append(node)
            # Find nodes that depend on this node
            for neighbor in self._reverse_graph.get(node, []):
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        if len(order) != len(nodes_to_resolve):
            raise ValueError("Cycle detected or missing dependencies in graph resolution.")

        return order

    def get_execution_plan(self, targets: List[str]) -> List[str]:
        """Generate a linear list of steps required to compute targets in order."""
        return self.topological_sort(target_nodes=targets)

    def get_reverse_dependencies(self, node: str) -> List[str]:
        """Find all features that depend (directly or indirectly) on this node."""
        dependent_nodes = set()
        queue = deque([node])
        while queue:
            curr = queue.popleft()
            for parent in self._reverse_graph.get(curr, []):
                if parent not in dependent_nodes:
                    dependent_nodes.add(parent)
                    queue.append(parent)
        return list(dependent_nodes)

    def get_impact_analysis(self, node: str) -> Dict[str, List[str]]:
        """Identify which modules/features are impacted if this feature changes."""
        impacted_features = self.get_reverse_dependencies(node)
        return {
            "impacted_features": impacted_features,
            "impacted_count": len(impacted_features)
        }
