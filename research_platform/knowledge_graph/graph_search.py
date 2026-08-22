"""Search Engine executing text keyword searches over node properties.
"""

from __future__ import annotations

from typing import Any, List

from research_platform.knowledge_graph.models import KnowledgeNode


class GraphSearchEngine:
    """Performs property value scans to discover relevant nodes."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def search_by_keyword(self, keyword: str) -> List[KnowledgeNode]:
        """Find nodes where properties or description contains keyword match."""
        nodes = self.repository.list_nodes()
        matches = []
        kw = keyword.lower()
        
        for n in nodes:
            for val in n.properties.values():
                if kw in str(val).lower():
                    matches.append(n)
                    break
        return matches
