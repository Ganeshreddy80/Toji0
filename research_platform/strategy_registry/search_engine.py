"""Search engine filtering strategy entries based on queries, tags, risk profiles.
"""

from __future__ import annotations

from typing import List
from research_platform.strategy_registry.interfaces import ISearchEngine
from research_platform.strategy_registry.models import RegisteredStrategy
from research_platform.strategy_registry.repository import StrategyRegistryRepository


class SearchEngine(ISearchEngine):
    """Filters registered strategies databases matching query bounds."""

    def __init__(self, repo: StrategyRegistryRepository) -> None:
        self._repo = repo

    def search(self, query: str) -> List[RegisteredStrategy]:
        strats = self._repo.list_strategies()
        if not query:
            return strats

        q = query.lower()
        results = []
        for s in strats:
            if (q in s.name.lower() or 
                q in s.description.lower() or 
                any(q in t.lower() for t in s.tags) or
                any(q in c.lower() for c in s.categories)):
                results.append(s)
        return results
