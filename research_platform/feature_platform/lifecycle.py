"""Feature Lifecycle promotion manager.
"""

from __future__ import annotations

import threading
from typing import Dict

from toji_platform.core.event_bus import IEventBus
from research_platform.feature_platform.events import (
    FeaturePromoted,
    FeatureRejected
)


class FeatureLifecycleManager:
    """Tracks and validates feature lifecycle status transitions."""

    VALID_TRANSITIONS = {
        "DRAFT": {"EXPERIMENTAL"},
        "EXPERIMENTAL": {"VALIDATED", "REJECTED"},
        "VALIDATED": {"APPROVED", "REJECTED"},
        "APPROVED": {"PRODUCTION", "DEPRECATED"},
        "PRODUCTION": {"DEPRECATED"},
        "DEPRECATED": {"ARCHIVED"},
        "ARCHIVED": set(),
        "REJECTED": {"DRAFT"}
    }

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._states: Dict[str, str] = {}  # feature_name -> state

    def set_state(self, name: str, state: str) -> None:
        """Set state directly (for testing/setup)."""
        with self._lock:
            self._states[name] = state.upper()

    def get_state(self, name: str) -> str:
        """Fetch current state."""
        with self._lock:
            return self._states.get(name, "DRAFT")

    def transition_state(self, name: str, target_state: str) -> None:
        """Transition a feature state.

        Raises:
            ValueError: If the transition violates lifecycle workflow path logic.
        """
        target = target_state.upper()
        with self._lock:
            current = self._states.get(name, "DRAFT")
            allowed = self.VALID_TRANSITIONS.get(current, set())
            
            if target not in allowed:
                raise ValueError(
                    f"Invalid lifecycle transition for '{name}': cannot go from {current} to {target}."
                )
            
            self._states[name] = target

        # Publish transitions
        if target == "PRODUCTION":
            self._event_bus.publish(FeaturePromoted(payload={"name": name}))
        elif target == "REJECTED":
            self._event_bus.publish(FeatureRejected(payload={"name": name, "reason": "Failed promotion checks."}))
