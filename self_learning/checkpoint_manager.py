"""Thread-safe In-Memory Checkpoint Manager for the Self Learning Engine (Sprint 11B)."""

from __future__ import annotations

import collections
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from self_learning.training_events import CheckpointSaved
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class CheckpointRecord(BaseModel):
    """Immutable record of a training checkpoint."""

    checkpoint_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str = Field(..., description="Associated pipeline identifier.")
    epoch: int = Field(default=0, ge=0)
    step: int = Field(default=0, ge=0)
    state_dict: Dict[str, Any] = Field(default_factory=dict, description="In-memory model/optimizer state.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class CheckpointManager:
    """Thread-safe in-memory Checkpoint Manager with bounded capacity (up to 1000 checkpoints)."""

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        max_checkpoints: int = 1000,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._max_checkpoints = max_checkpoints
        # checkpoint_id -> CheckpointRecord
        self._checkpoints: Dict[str, CheckpointRecord] = {}
        # pipeline_id -> list of checkpoint_ids
        self._pipeline_index: Dict[str, List[str]] = collections.defaultdict(list)

    def save_checkpoint(
        self,
        pipeline_id: str,
        epoch: int = 0,
        step: int = 0,
        state_dict: Optional[Dict[str, Any]] = None,
    ) -> CheckpointRecord:
        """Save a new in-memory checkpoint."""
        with self._lock:
            if len(self._checkpoints) >= self._max_checkpoints:
                # Evict oldest checkpoint
                oldest_id = next(iter(self._checkpoints))
                self.delete_checkpoint(oldest_id)

            record = CheckpointRecord(
                pipeline_id=pipeline_id,
                epoch=epoch,
                step=step,
                state_dict=state_dict or {},
            )
            self._checkpoints[record.checkpoint_id] = record
            self._pipeline_index[pipeline_id].append(record.checkpoint_id)

            logger.info("Saved checkpoint '%s' for pipeline '%s' (epoch=%d)", record.checkpoint_id, pipeline_id, epoch)

            if self._event_bus:
                self._event_bus.publish(
                    CheckpointSaved(
                        checkpoint_id=record.checkpoint_id,
                        pipeline_id=pipeline_id,
                        epoch=epoch,
                    )
                )
            return record

    def load_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointRecord]:
        """Load a checkpoint by ID."""
        with self._lock:
            return self._checkpoints.get(checkpoint_id)

    def list_checkpoints(self, pipeline_id: Optional[str] = None) -> List[CheckpointRecord]:
        """List all checkpoints, optionally filtered by pipeline_id."""
        with self._lock:
            if pipeline_id:
                cids = self._pipeline_index.get(pipeline_id, [])
                return [self._checkpoints[cid] for cid in cids if cid in self._checkpoints]
            return list(self._checkpoints.values())

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint by ID."""
        with self._lock:
            record = self._checkpoints.pop(checkpoint_id, None)
            if record is None:
                return False
            cids = self._pipeline_index.get(record.pipeline_id, [])
            if checkpoint_id in cids:
                cids.remove(checkpoint_id)
            logger.info("Deleted checkpoint '%s'", checkpoint_id)
            return True

    def count(self) -> int:
        """Return count of stored checkpoints."""
        with self._lock:
            return len(self._checkpoints)

    def clear(self) -> None:
        """Clear all stored checkpoints."""
        with self._lock:
            self._checkpoints.clear()
            self._pipeline_index.clear()
