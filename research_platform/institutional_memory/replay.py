"""Replay Engine compiling historical context parameters snapshots.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from research_platform.institutional_memory.interfaces import IDeterministicReplayEngine
from research_platform.institutional_memory.models import (
    PositionMemory,
    ReplaySnapshot,
    RiskMemory,
    StrategyMemory,
    TradeMemory
)


class DeterministicReplayEngine(IDeterministicReplayEngine):
    """Query memory tables to extract parameters context at target timestamps."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def reconstruct_state(self, ts: datetime) -> ReplaySnapshot:
        """Query memory log history before timestamp and compile snapshot."""
        memories = self.repository.get_memories_at_timestamp(ts)
        
        # Sort and select relevant memories
        trades: List[TradeMemory] = memories.get("trades", [])
        positions: List[PositionMemory] = memories.get("positions", [])
        strategies: List[StrategyMemory] = memories.get("strategies", [])
        risks: List[RiskMemory] = memories.get("risks", [])

        return ReplaySnapshot(
            snapshot_timestamp=ts,
            trades=trades,
            positions=positions,
            strategies=strategies,
            risks=risks
        )
