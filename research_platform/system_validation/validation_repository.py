"""Thread-safe, append-only repository for storing validation outcomes.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.system_validation.interfaces import IValidationRepository
from research_platform.system_validation.models import (
    SubsystemHealth,
    SystemCertificationCard,
)


class ValidationRepository(IValidationRepository):
    """Memory-backed, thread-safe repository implementation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._health: Dict[str, SubsystemHealth] = {}
        self._certs: List[SystemCertificationCard] = []

    def save_health(self, health: SubsystemHealth) -> None:
        with self._lock:
            self._health[health.name] = health

    def list_health_cards(self) -> List[SubsystemHealth]:
        with self._lock:
            return list(self._health.values())

    def save_certification(self, cert: SystemCertificationCard) -> None:
        with self._lock:
            self._certs.append(cert)

    def get_latest_certification(self) -> Optional[SystemCertificationCard]:
        with self._lock:
            if not self._certs:
                return None
            return self._certs[-1]
