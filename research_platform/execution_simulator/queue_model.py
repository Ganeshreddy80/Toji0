"""Queue model simulating order queue priority inside a spread level.
"""

from __future__ import annotations


class QueueModel:
    """Calculates order queue position shifts."""

    def calculate_queue_place(self, size_ahead: float, incoming_size: float) -> float:
        # returns percent chance of order getting matched
        total = size_ahead + incoming_size
        if total <= 0.0:
            return 1.0
        return 1.0 - (size_ahead / total)
