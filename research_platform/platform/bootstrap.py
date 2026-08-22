"""Platform bootstrap helper.
"""

from __future__ import annotations

import logging
from research_platform.platform.application import PlatformApplication
from research_platform.platform.state import PlatformState

logger = logging.getLogger(__name__)


def bootstrap_platform() -> PlatformApplication:
    """Helper method to construct and boot the platform application instance."""
    existing = PlatformState.get()
    if existing:
        logger.warning("Duplicate boot blocked")
        return existing

    app = PlatformApplication()
    app.boot()
    
    return PlatformState.set(app)
