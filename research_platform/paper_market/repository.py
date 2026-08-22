"""Repository storing paper market parameters configurations.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional


class PaperMarketRepository:
    """Memory-backed, thread-safe configuration repository."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._configs: Dict[str, str] = {}

    def set_config(self, key: str, value: str) -> None:
        with self._lock:
            self._configs[key] = value

    def get_config(self, key: str) -> Optional[str]:
        with self._lock:
            return self._configs.get(key)
