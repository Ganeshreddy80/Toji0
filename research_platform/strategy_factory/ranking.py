"""Strategy factory candidate ranker based on metrics scorecards.
"""

from __future__ import annotations
from typing import List, Dict, Any

class StrategyRanker:
    """Ranks trading strategy candidates by performance metrics."""

    def rank_strategies(self, scored_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort strategies in descending order of their global score."""
        return sorted(scored_candidates, key=lambda x: x.get("score", 0.0), reverse=True)
