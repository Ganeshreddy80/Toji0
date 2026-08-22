"""Shutdown manager executing cleanup steps.
"""

from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)


class ShutdownManager:
    """Invokes shutdown sequence triggers across subsystems."""

    def shutdown_subsystems(self, plugins: List[Any]) -> bool:
        for plugin in plugins:
            try:
                plugin.shutdown()
            except Exception as e:
                logger.error("Shutdown Failure: Failed to shutdown plugin %s: %s", plugin, e)
        return True
from typing import Any
