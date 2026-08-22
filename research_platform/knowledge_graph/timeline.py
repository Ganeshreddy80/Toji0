"""Timeline Engine compiling chronological events logs.
"""

from __future__ import annotations

from typing import List

from research_platform.knowledge_graph.models import TimelineResult


class TimelineEngine:
    """Sorts knowledge graph nodes chronologically."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def compile_timeline(self) -> List[TimelineResult]:
        """Compile a list of timeline results sorted by timestamp."""
        nodes = self.repository.list_nodes()
        results = []
        
        for n in nodes:
            results.append(
                TimelineResult(
                    event_name=f"{n.node_type}_REGISTERED",
                    timestamp=n.created_at,
                    properties=n.properties
                )
            )

        # Sort chronologically
        results.sort(key=lambda x: x.timestamp)
        return results
