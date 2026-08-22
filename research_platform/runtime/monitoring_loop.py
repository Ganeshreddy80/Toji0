"""Monitoring Loop subsystem implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from research_platform.runtime.interfaces import IRuntimeLoop

logger = logging.getLogger(__name__)


class MonitoringLoop(IRuntimeLoop):
    """Probes components telemetry and tracks response latencies."""

    def __init__(self, container: Any) -> None:
        self.container = container
        self.retry_count = 0

    def execute(self, context: Dict[str, Any]) -> None:
        logger.debug("Executing MonitoringLoop telemetry evaluations...")
        try:
            monitor = self.container.resolve("MonitoringOrchestrator")
            if monitor and hasattr(monitor, "aggregate_health"):
                monitor.aggregate_health()
        except Exception:
            pass

    def recover(self, exception: Exception) -> bool:
        self.retry_count += 1
        logger.warning("MonitoringLoop caught exception: %s. Recovery retry: %d", exception, self.retry_count)
        return True
