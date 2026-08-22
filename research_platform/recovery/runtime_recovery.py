"""Runtime engine recovery manager.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class RuntimeRecoveryManager:
    """Restores continuous loop status, run counters, and telemetry metrics."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def restore_runtime(self, runtime_data: Dict[str, Any]) -> None:
        """Apply target engine parameters to the background thread orchestrator."""
        logger.info("Restoring Continuous Runtime loop state parameters...")
        try:
            engine = self.container.resolve("RuntimeEngine")
            if engine and hasattr(engine, "restore_from_state"):
                engine.restore_from_state(runtime_data)
        except Exception as e:
            logger.warning("Runtime engine state restore failed or was bypassed: %s", e)
