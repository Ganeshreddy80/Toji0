"""Database repositories for validation runs and reports.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.validation_core.interfaces import IValidationRepository
from research_platform.validation_core.models import ValidationRun


class ValidationRepository(IValidationRepository):
    """Memory repository for saving and loading validation runs and reports."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._db: Dict[str, ValidationRun] = {}

    def save_run(self, run: ValidationRun) -> None:
        """Persist validation run progress or result."""
        with self._lock:
            self._db[run.run_id] = run

    def get_run(self, run_id: str) -> Optional[ValidationRun]:
        """Fetch validation run by unique ID."""
        with self._lock:
            return self._db.get(run_id)

    def list_runs(self) -> List[ValidationRun]:
        """Fetch all validation runs."""
        with self._lock:
            return list(self._db.values())
