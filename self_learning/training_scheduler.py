"""Thread-safe Priority Scheduler with FIFO ordering inside equal priority levels (Sprint 11B)."""

from __future__ import annotations

import heapq
import logging
import threading
from typing import Dict, List, Optional, Set, Tuple

from self_learning.pipeline_state import PipelineConfig

logger = logging.getLogger(__name__)

# Entry in heap: (-priority, sequence_number, pipeline_id, config)
QueueItem = Tuple[int, int, str, PipelineConfig]


class TrainingScheduler:
    """Thread-safe priority queue scheduler for training pipelines.

    Uses heapq for O(log n) insertion and extraction.
    Higher priority value is popped first. Equal priority items are ordered FIFO via monotonic sequence numbers.
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        self._lock = threading.RLock()
        self._max_size = max_queue_size
        self._heap: List[QueueItem] = []
        self._counter: int = 0  # Monotonic FIFO sequence generator
        self._queued_ids: Set[str] = set()
        self._cancelled_ids: Set[str] = set()

    def queue_job(self, config: PipelineConfig) -> bool:
        """Queue a pipeline configuration for execution. O(log n)."""
        with self._lock:
            if len(self._queued_ids) >= self._max_size:
                logger.warning("TrainingScheduler queue full (max=%d)", self._max_size)
                return False

            if config.pipeline_id in self._queued_ids:
                logger.warning("Pipeline '%s' is already in the queue", config.pipeline_id)
                return False

            self._counter += 1
            # Priority inverted for min-heap
            item: QueueItem = (-config.priority, self._counter, config.pipeline_id, config)
            heapq.heappush(self._heap, item)
            self._queued_ids.add(config.pipeline_id)
            self._cancelled_ids.discard(config.pipeline_id)

            logger.info("Queued pipeline '%s' (priority=%d, seq=%d)", config.pipeline_id, config.priority, self._counter)
            return True

    def pop_next_job(self) -> Optional[PipelineConfig]:
        """Pop and return the highest priority queued job. O(log n)."""
        with self._lock:
            while self._heap:
                neg_prio, seq, pid, config = heapq.heappop(self._heap)
                self._queued_ids.discard(pid)

                if pid in self._cancelled_ids:
                    self._cancelled_ids.discard(pid)
                    logger.info("Discarded cancelled pipeline '%s' from scheduler heap", pid)
                    continue

                logger.info("Popped next pipeline '%s' (priority=%d)", pid, config.priority)
                return config

            return None

    def cancel_queued_job(self, pipeline_id: str) -> bool:
        """Cancel a queued job by pipeline ID."""
        with self._lock:
            if pipeline_id in self._queued_ids:
                self._queued_ids.discard(pipeline_id)
                self._cancelled_ids.add(pipeline_id)
                logger.info("Marked pipeline '%s' as cancelled in scheduler queue", pipeline_id)
                return True
            return False

    def is_queued(self, pipeline_id: str) -> bool:
        """Check if a pipeline is currently queued."""
        with self._lock:
            return pipeline_id in self._queued_ids and pipeline_id not in self._cancelled_ids

    def queue_size(self) -> int:
        """Return number of valid queued jobs."""
        with self._lock:
            return len(self._queued_ids - self._cancelled_ids)

    def peek_queue(self) -> List[PipelineConfig]:
        """Return list of queued configs ordered by priority without popping."""
        with self._lock:
            valid_items = [
                item for item in sorted(self._heap)
                if item[2] in self._queued_ids and item[2] not in self._cancelled_ids
            ]
            return [item[3] for item in valid_items]

    def clear(self) -> None:
        """Clear all queued jobs."""
        with self._lock:
            self._heap.clear()
            self._queued_ids.clear()
            self._cancelled_ids.clear()
            self._counter = 0
