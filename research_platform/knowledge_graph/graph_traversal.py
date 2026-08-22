"""Traversal Engine executing DFS paths validation and cycles checks.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Set

from research_platform.knowledge_graph.interfaces import IGraphTraversalEngine
from research_platform.knowledge_graph.models import KnowledgeEdge, TraversalResult


class GraphTraversalEngine(IGraphTraversalEngine):
    """Executes DFS/BFS multi-hop traversal paths queries."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def traverse_path(self, start_node_id: str, target_node_id: str) -> TraversalResult:
        """Execute BFS paths query to find nodes links path."""
        edges = self.repository.list_edges()
        
        # Build adjacency maps
        adj: Dict[str, List[KnowledgeEdge]] = {}
        for e in edges:
            if e.source_id not in adj:
                adj[e.source_id] = []
            adj[e.source_id].append(e)

        # BFS Queue holds (current_node, path_of_edges)
        queue = deque([(start_node_id, [])])
        visited: Set[str] = {start_node_id}

        while queue:
            curr, path = queue.popleft()
            if curr == target_node_id:
                visited_nodes = [start_node_id] + [e.target_id for e in path]
                return TraversalResult(visited_node_ids=visited_nodes, edges_traversed=path)

            for edge in adj.get(curr, []):
                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    queue.append((edge.target_id, path + [edge]))

        return TraversalResult()

    def detect_cycles(self) -> bool:
        """Standard DFS cycle detection algorithm."""
        edges = self.repository.list_edges()
        adj: Dict[str, List[str]] = {}
        for e in edges:
            if e.source_id not in adj:
                adj[e.source_id] = []
            adj[e.source_id].append(e.target_id)

        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        nodes = self.repository.list_nodes()
        for node in nodes:
            if node.node_id not in visited:
                if dfs(node.node_id):
                    return True
        return False
