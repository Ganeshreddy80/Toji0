"""Ranking engine compiling strategy leaderboards based on metrics scores.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from research_platform.experiment_manager.interfaces import IRankingEngine
from research_platform.experiment_manager.models import Leaderboard, LeaderboardEntry, Experiment


class RankingEngine(IRankingEngine):
    """Sorts strategy outputs based on score performance card indicators."""

    def rank_strategies(self, name: str, experiments: List[Experiment]) -> Leaderboard:
        entries = []
        for exp in experiments:
            # Score logic based on returns or mock Sharpe metric
            pnl = exp.results.get("pnl", 0.0)
            sharpe = exp.results.get("sharpe_ratio", 0.0)
            score = pnl * (1.0 + sharpe)
            
            entries.append((exp.experiment_id, score))

        # Sort descending by score
        entries.sort(key=lambda x: x[1], reverse=True)
        
        ranked_entries = [
            LeaderboardEntry(strategy_id=e_id, score=score, rank=idx + 1)
            for idx, (e_id, score) in enumerate(entries)
        ]

        return Leaderboard(
            name=name,
            entries=ranked_entries,
            updated_at=datetime.now(timezone.utc)
        )
