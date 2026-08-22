"""Plugin manager implementation.

``PluginManager`` handles loading, dependency-ordered initialization,
and shutdown of Toji plugins.
"""

from __future__ import annotations

import time
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from toji_platform.core.errors import (
    PluginDependencyError,
    PluginLoadError,
    PluginNotFoundError,
)
from toji_platform.core.plugin_manager.interfaces import IPlugin, IPluginManager
from toji_platform.core.types import HealthStatus, ModuleState, PluginId

logger = logging.getLogger(__name__)


class PluginManager(IPluginManager):
    """Default plugin manager with topological dependency ordering.

    Plugins declare their ``dependencies`` — a list of ``PluginId``
    values that must be initialised first.  ``initialize_all`` resolves
    the ordering automatically.
    """

    def __init__(self) -> None:
        self._plugins: dict[PluginId, IPlugin] = {}
        # Track stats for each plugin
        self._stats: dict[PluginId, dict[str, Any]] = defaultdict(lambda: {
            "state": "created",
            "startup_timestamp": None,
            "uptime": 0.0,
            "last_heartbeat": None,
            "startup_duration_ms": 0.0,
            "shutdown_duration_ms": 0.0,
            "initialization_errors": None,
        })

    # ── IPluginManager ─────────────────────────────────────────────────

    def load(self, plugin: IPlugin) -> None:
        pid = plugin.plugin_id
        if pid in self._plugins:
            raise PluginLoadError(
                plugin.name, f"Plugin '{pid}' is already loaded"
            )
        self._plugins[pid] = plugin
        self._stats[pid]["state"] = "created"
        logger.info("Plugin loaded: %s v%s", plugin.name, plugin.version)

    def unload(self, plugin_id: PluginId) -> None:
        if plugin_id not in self._plugins:
            raise PluginNotFoundError(plugin_id)
        plugin = self._plugins[plugin_id]
        if plugin.state not in (ModuleState.STOPPED, ModuleState.CREATED):
            try:
                plugin.shutdown()
            except Exception:
                logger.exception(
                    "Error shutting down plugin '%s' during unload", plugin.name
                )
        self._plugins.pop(plugin_id)
        self._stats.pop(plugin_id, None)
        logger.info("Plugin unloaded: %s", plugin.name)

    def get(self, plugin_id: PluginId) -> IPlugin:
        if plugin_id not in self._plugins:
            raise PluginNotFoundError(plugin_id)
        return self._plugins[plugin_id]

    def list_plugins(self) -> list[IPlugin]:
        return list(self._plugins.values())

    def initialize_all(self) -> None:
        """Initialize plugins in topological (dependency) order."""
        order = self._resolve_order()
        for pid in order:
            plugin = self._plugins[pid]
            stats = self._stats[pid]
            stats["state"] = "initializing"
            start_time = time.perf_counter()
            stats["startup_timestamp"] = datetime.now(timezone.utc).isoformat()
            try:
                stats["state"] = "starting"
                plugin.initialize()
                stats["startup_duration_ms"] = (time.perf_counter() - start_time) * 1000.0
                stats["state"] = "running"
                logger.info("Plugin initialised: %s", plugin.name)
            except Exception as exc:
                stats["state"] = "failed"
                stats["initialization_errors"] = str(exc)
                raise PluginLoadError(plugin.name, str(exc)) from exc

    def shutdown_all(self) -> None:
        """Shut down plugins in reverse dependency order."""
        try:
            order = self._resolve_order()
        except PluginDependencyError as exc:
            logger.warning(
                "Dependency sorting failed during shutdown: %s. Falling back to reversed load order.",
                exc,
            )
            order = list(self._plugins.keys())

        for pid in reversed(order):
            plugin = self._plugins[pid]
            stats = self._stats[pid]
            stats["state"] = "stopping"
            start_time = time.perf_counter()
            try:
                plugin.shutdown()
                stats["shutdown_duration_ms"] = (time.perf_counter() - start_time) * 1000.0
                stats["state"] = "stopped"
                logger.info("Plugin shut down: %s", plugin.name)
            except Exception as exc:
                stats["state"] = "failed"
                stats["shutdown_duration_ms"] = (time.perf_counter() - start_time) * 1000.0
                logger.exception(
                    "Error shutting down plugin '%s'", plugin.name
                )

    def health_check_all(self) -> dict[PluginId, HealthStatus]:
        return {
            pid: plugin.health_check()
            for pid, plugin in self._plugins.items()
        }

    def get_plugin_lifecycle_stats(self) -> dict[str, dict[str, Any]]:
        """Retrieve execution and lifecycle statistics for all plugins."""
        result = {}
        for pid, stats in self._stats.items():
            stats_copy = dict(stats)
            if stats["state"] == "running" and stats["startup_timestamp"]:
                start_dt = datetime.fromisoformat(stats["startup_timestamp"])
                stats_copy["uptime"] = (datetime.now(timezone.utc) - start_dt).total_seconds()
            result[str(pid)] = stats_copy
        return result

    # ── Dependency resolution ──────────────────────────────────────────

    def _resolve_order(self) -> list[PluginId]:
        """Kahn's algorithm for topological sort.

        Raises:
            PluginDependencyError: on missing deps or cycles.
        """
        # Validate all dependencies exist
        for pid, plugin in self._plugins.items():
            missing = [
                d for d in plugin.dependencies if d not in self._plugins
            ]
            if missing:
                raise PluginDependencyError(plugin.name, missing)

        # Build adjacency + in-degree
        in_degree: dict[PluginId, int] = {pid: 0 for pid in self._plugins}
        dependents: dict[PluginId, list[PluginId]] = defaultdict(list)

        for pid, plugin in self._plugins.items():
            for dep in plugin.dependencies:
                dependents[dep].append(pid)
                in_degree[pid] += 1

        # BFS
        queue = [pid for pid, deg in in_degree.items() if deg == 0]
        order: list[PluginId] = []

        while queue:
            current = queue.pop(0)
            order.append(current)
            for dependent in dependents[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(order) != len(self._plugins):
            raise PluginDependencyError(
                "PluginManager",
                ["Circular dependency detected among plugins"],
            )

        return order
