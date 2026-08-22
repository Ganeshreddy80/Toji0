"""Plugin loader implementing auto-discovery of all platform plugins.
"""

from __future__ import annotations

import os
import importlib
import inspect
import logging
from typing import Any, List

logger = logging.getLogger(__name__)


class PluginLoader:
    """Discovers and imports plugin classes under research_platform package structure."""

    def discover_plugins(self, container: Any) -> List[Any]:
        plugins = []
        plugins_failed: List[str] = []

        # Base path of research_platform directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # List subdirectories under research_platform
        for entry in os.listdir(base_dir):
            entry_path = os.path.join(base_dir, entry)
            if os.path.isdir(entry_path) and not entry.startswith(".") and entry != "__pycache__":
                plugin_file = os.path.join(entry_path, "plugin.py")
                if os.path.exists(plugin_file):
                    import_path = f"research_platform.{entry}.plugin"
                    try:
                        module = importlib.import_module(import_path)
                        # Find classes ending with Plugin or matching the naming convention
                        for name, obj in inspect.getmembers(module, inspect.isclass):
                            if name.endswith("Plugin") and obj.__module__ == import_path:
                                logger.info("Discovered plugin class %s in %s", name, import_path)
                                # Instantiate plugin with DI container
                                instance = obj(container)
                                plugins.append(instance)
                    except Exception as e:
                        logger.error(
                            "Plugin discovery failure [%s]: %s",
                            import_path, e,
                            exc_info=True
                        )
                        plugins_failed.append(import_path)

        if plugins_failed:
            logger.warning(
                "PluginLoader: %d plugin module(s) failed to import: %s",
                len(plugins_failed), ", ".join(plugins_failed)
            )

        return plugins
