"""Alpha Registry module.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.alpha_factory.models import AlphaRegistryEntry


class AlphaRegistry:
    """Thread-safe index mapping alpha factor definitions, versions, and mutations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: Dict[str, AlphaRegistryEntry] = {}

    def register(self, entry: AlphaRegistryEntry) -> None:
        """Add an alpha entry to the registry."""
        with self._lock:
            self._entries[entry.candidate_id] = entry

    def get(self, candidate_id: str) -> Optional[AlphaRegistryEntry]:
        """Load registered alpha details."""
        with self._lock:
            return self._entries.get(candidate_id)

    def list_all(self) -> List[AlphaRegistryEntry]:
        """List all registered alphas."""
        with self._lock:
            return list(self._entries.values())
