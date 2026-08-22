"""Thread-safe Leaderboard System for Model Ranking with Stable Tie-Breaking (Sprint 11C)."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from self_learning.evaluation_events import LeaderboardUpdated
from self_learning.evaluation_metrics import MetricResult
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class LeaderboardEntry(BaseModel):
    """Immutable entry representing a ranked model on a leaderboard."""

    rank: int = Field(..., ge=1, description="1-based rank position.")
    model_id: str = Field(..., description="Target model identifier.")
    metric_name: str = Field(..., description="Primary ranking metric name.")
    metric_value: float = Field(..., description="Ranked metric value.")
    evaluation_id: str = Field(..., description="Source evaluation ID.")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class Leaderboard:
    """Thread-safe Leaderboard supporting metric-based ranking and stable tie-breaking."""

    LOWER_IS_BETTER = {"val_loss", "inference_latency_ms", "loss"}

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        max_entries_per_board: int = 200,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._max_entries = max_entries_per_board
        # leaderboard_name -> list of LeaderboardEntry
        self._boards: Dict[str, List[LeaderboardEntry]] = {}

    def update_ranking(
        self,
        leaderboard_name: str,
        metrics_list: List[MetricResult],
        metric_name: str = "accuracy",
    ) -> List[LeaderboardEntry]:
        """Update leaderboard ranking for a given metric. Stable ordering for ties via model_id."""
        with self._lock:
            if not metrics_list:
                return self._boards.get(leaderboard_name, [])

            lower_better = metric_name in self.LOWER_IS_BETTER

            def get_val(m: MetricResult) -> float:
                return float(getattr(m, metric_name, 0.0))

            # Stable sort key: (-value, model_id) for higher-is-better; (value, model_id) for lower-is-better
            sorted_metrics = sorted(
                metrics_list,
                key=lambda m: (
                    get_val(m) if lower_better else -get_val(m),
                    m.model_id,
                ),
            )

            # Deduplicate by model_id (keep best metric per model)
            seen_models: set = set()
            unique_metrics: List[MetricResult] = []
            for m in sorted_metrics:
                if m.model_id not in seen_models:
                    seen_models.add(m.model_id)
                    unique_metrics.append(m)

            entries: List[LeaderboardEntry] = []
            for idx, m in enumerate(unique_metrics[: self._max_entries], start=1):
                entry = LeaderboardEntry(
                    rank=idx,
                    model_id=m.model_id,
                    metric_name=metric_name,
                    metric_value=get_val(m),
                    evaluation_id=m.evaluation_id,
                )
                entries.append(entry)

            self._boards[leaderboard_name] = entries

            top_id = entries[0].model_id if entries else "none"
            logger.info("Updated leaderboard '%s' with %d entries (top='%s')", leaderboard_name, len(entries), top_id)

            if self._event_bus and entries:
                self._event_bus.publish(
                    LeaderboardUpdated(
                        leaderboard_name=leaderboard_name,
                        top_model_id=top_id,
                        ranked_count=len(entries),
                    )
                )
            return list(entries)

    def get_top_models(self, leaderboard_name: str, top_k: int = 10) -> List[LeaderboardEntry]:
        """Get top K models for a leaderboard."""
        with self._lock:
            board = self._boards.get(leaderboard_name, [])
            return list(board[: max(1, top_k)])

    def get_model_rank(self, leaderboard_name: str, model_id: str) -> Optional[int]:
        """Get current 1-based rank of a model on a leaderboard."""
        with self._lock:
            board = self._boards.get(leaderboard_name, [])
            for entry in board:
                if entry.model_id == model_id:
                    return entry.rank
            return None

    def list_leaderboards(self) -> List[str]:
        """List names of active leaderboards."""
        with self._lock:
            return list(self._boards.keys())

    def clear(self) -> None:
        """Clear all leaderboards."""
        with self._lock:
            self._boards.clear()
