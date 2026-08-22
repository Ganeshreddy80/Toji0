"""Visualization Engine formatting Mermaid diagram structures.
"""

from __future__ import annotations


class GraphVisualizer:
    """Constructs flowchart schemas strings."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def render_mermaid(self) -> str:
        """Format current active graph as standard Mermaid flowdiagram string."""
        nodes = self.repository.list_nodes()
        edges = self.repository.list_edges()

        lines = ["graph TD"]
        
        # Nodes
        for n in nodes:
            lines.append(f'  {n.node_id}["{n.node_id} ({n.node_type})"]')

        # Edges
        for e in edges:
            lines.append(f"  {e.source_id} -->|{e.relationship_type}| {e.target_id}")

        return "\n".join(lines)
