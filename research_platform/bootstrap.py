"""Unified entry point for bootstrapping the TOJI Quantitative Research Platform.
"""

from __future__ import annotations

import logging
from typing import Any

from research_platform.platform.application import PlatformApplication
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.platform.state import PlatformState

logger = logging.getLogger(__name__)


def bootstrap_platform() -> PlatformApplication:
    """Bootstraps and returns the global PlatformApplication instance."""
    existing = PlatformState.get()
    if existing:
        logger.warning("Duplicate boot blocked")
        return existing

    # Import the platform bootstrap helper dynamically/statically to boot it
    from research_platform.platform.bootstrap import bootstrap_platform as platform_bootstrap
    app = platform_bootstrap()
    PlatformState.set(app)
    return app


def shutdown_platform() -> None:
    """Gracefully shuts down the bootstrapped platform."""
    if not PlatformState.exists():
        logger.warning("No active TOJI Platform instance to shutdown.")
        return

    logger.info("Stopping TOJI Quantitative Research Platform...")
    kernel = PlatformState.get()
    kernel.shutdown()
    with PlatformState._lock:
        PlatformState._kernel = None


def get_service(name: str) -> Any:
    """Helper utility to retrieve a singleton service from the platform registry."""
    return ServiceRegistry().get_service(name)
