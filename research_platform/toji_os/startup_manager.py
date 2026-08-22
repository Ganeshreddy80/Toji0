"""Startup manager bootstrapping core modules.
"""

from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)


class StartupManager:
    """Invokes initializers across all target subsystem plugins."""

    def boot_subsystems(self, plugins: List[Any]) -> bool:
        # Enforce initializations
        for plugin in plugins:
            try:
                plugin.initialize()
            except Exception as e:
                logger.error("Startup Failure: Failed to boot plugin %s: %s", plugin, e)
                return False
        return True
from typing import Any
