"""Thread-safe memory repository caching walk forward optimization windows and overfitting cards.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional
from research_platform.walk_forward.interfaces import IWalkForwardRepository
from research_platform.walk_forward.models import ValidationWindow, SensitivityScore, OverfittingCard


class WalkForwardRepository(IWalkForwardRepository):
    """Memory-backed, thread-safe repository for walk forward validation configurations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: Dict[str, ValidationWindow] = {}
        self._sensitivities: Dict[str, SensitivityScore] = {}
        self._overfittings: Dict[str, OverfittingCard] = {}

    def save_window(self, window: ValidationWindow) -> None:
        with self._lock:
            self._windows[window.window_id] = window

    def get_window(self, window_id: str) -> Optional[ValidationWindow]:
        with self._lock:
            return self._windows.get(window_id)

    def save_sensitivity(self, score: SensitivityScore) -> None:
        with self._lock:
            self._sensitivities[score.parameter_name] = score

    def get_sensitivity(self, parameter_name: str) -> Optional[SensitivityScore]:
        with self._lock:
            return self._sensitivities.get(parameter_name)

    def save_overfitting(self, card: OverfittingCard) -> None:
        with self._lock:
            self._overfittings[card.strategy_id] = card

    def get_overfitting(self, strategy_id: str) -> Optional[OverfittingCard]:
        with self._lock:
            return self._overfittings.get(strategy_id)
