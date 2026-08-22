"""Thread-safe memory repository caching alpha signals, combinations, ensembles.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional
from research_platform.alpha_factory.interfaces import IAlphaFactoryRepository
from research_platform.alpha_factory.models import AlphaSignal, AlphaCombo, EnsembleModel


class AlphaFactoryRepository(IAlphaFactoryRepository):
    """Memory-backed, thread-safe repository for alpha factory configurations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._signals: Dict[str, AlphaSignal] = {}
        self._combos: Dict[str, AlphaCombo] = {}
        self._ensembles: Dict[str, EnsembleModel] = {}

    def save_signal(self, signal: AlphaSignal) -> None:
        with self._lock:
            self._signals[signal.signal_id] = signal

    def get_signal(self, signal_id: str) -> Optional[AlphaSignal]:
        with self._lock:
            return self._signals.get(signal_id)

    def save_combo(self, combo: AlphaCombo) -> None:
        with self._lock:
            self._combos[combo.combo_id] = combo

    def get_combo(self, combo_id: str) -> Optional[AlphaCombo]:
        with self._lock:
            return self._combos.get(combo_id)

    def save_ensemble(self, model: EnsembleModel) -> None:
        with self._lock:
            self._ensembles[model.ensemble_id] = model

    def get_ensemble(self, ensemble_id: str) -> Optional[EnsembleModel]:
        with self._lock:
            return self._ensembles.get(ensemble_id)
