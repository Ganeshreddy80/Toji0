"""Lifecycle manager implementation.

``LifecycleManager`` maintains an ordered list of components and
orchestrates startup (in registration order) and shutdown (in
reverse order).  It also aggregates health-check results.
"""

from __future__ import annotations

import logging

from toji_platform.core.errors import ShutdownError, StartupError
from toji_platform.core.lifecycle.interfaces import IHealthCheck, ILifecycle
from toji_platform.core.types import HealthStatus

logger = logging.getLogger(__name__)


class LifecycleManager:
    """Orchestrates ordered startup, shutdown, and health probes.

    Components are started in the order they were registered and
    stopped in reverse order (LIFO) to respect dependency chains.
    """

    def __init__(self) -> None:
        self._components: list[ILifecycle] = []
        self._health_checks: list[IHealthCheck] = []
        self._started: bool = False

    # ── Registration ───────────────────────────────────────────────────

    def register(self, component: ILifecycle) -> None:
        """Add a component to the managed lifecycle."""
        self._components.append(component)
        if isinstance(component, IHealthCheck):
            self._health_checks.append(component)
        logger.debug("Lifecycle: registered '%s'", component.name)

    # ── Startup ────────────────────────────────────────────────────────

    def start_all(self) -> None:
        """Start all registered components in order.

        Raises:
            StartupError: if any component fails to start.
        """
        logger.info("Lifecycle: starting %d components", len(self._components))
        for component in self._components:
            try:
                component.start()
                logger.info("  ✓ Started '%s'", component.name)
            except Exception as exc:
                raise StartupError(
                    f"Component '{component.name}' failed to start: {exc}"
                ) from exc
        self._started = True
        logger.info("Lifecycle: all components started")

    # ── Shutdown ───────────────────────────────────────────────────────

    def stop_all(self) -> None:
        """Stop all components in reverse registration order.

        Collects errors rather than failing on the first one.
        """
        errors: list[str] = []
        logger.info("Lifecycle: stopping %d components", len(self._components))
        for component in reversed(self._components):
            try:
                component.stop()
                logger.info("  ✓ Stopped '%s'", component.name)
            except Exception as exc:
                msg = f"Component '{component.name}' failed to stop: {exc}"
                logger.error("  ✗ %s", msg)
                errors.append(msg)
        self._started = False
        if errors:
            raise ShutdownError(
                f"{len(errors)} component(s) failed to shut down: "
                + "; ".join(errors)
            )
        logger.info("Lifecycle: all components stopped")

    # ── Health ─────────────────────────────────────────────────────────

    def health_check(self) -> dict[str, HealthStatus]:
        """Run health checks across all checkable components."""
        results: dict[str, HealthStatus] = {}
        for check in self._health_checks:
            name = (
                check.name
                if hasattr(check, "name")
                else type(check).__name__
            )
            try:
                results[name] = check.check_health()
            except Exception:
                results[name] = HealthStatus.UNHEALTHY
        return results

    @property
    def is_started(self) -> bool:
        """Return ``True`` if ``start_all`` has been called."""
        return self._started

    @property
    def component_count(self) -> int:
        """Return the number of registered components."""
        return len(self._components)
