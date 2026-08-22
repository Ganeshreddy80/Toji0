"""Portfolio Governor plugin registration.

Reads all config from environment variables so tuning requires no code change:

  PG_MAX_POSITIONS          (default: 5)
  PG_MAX_EXPOSURE_PCT       (default: 0.80)
  PG_MAX_SYMBOL_PCT         (default: 0.25)
  PG_COOLDOWN_SECONDS       (default: 300)
  PG_ALLOW_OPPOSITE_SIDE    (default: false)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from research_platform.portfolio_governor.governor import PortfolioGovernor
from research_platform.portfolio_governor.models import GovernorConfig

logger = logging.getLogger(__name__)


class PortfolioGovernorPlugin:
    """Hooks the Portfolio Governor into the DI container during TOJI boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Build config from env vars, create governor, register in container."""
        config = GovernorConfig(
            max_open_positions=int(os.getenv("PG_MAX_POSITIONS", "5")),
            max_portfolio_exposure_pct=float(os.getenv("PG_MAX_EXPOSURE_PCT", "0.80")),
            max_symbol_exposure_pct=float(os.getenv("PG_MAX_SYMBOL_PCT", "0.25")),
            default_cooldown_seconds=float(os.getenv("PG_COOLDOWN_SECONDS", "300")),
            allow_opposite_side=os.getenv("PG_ALLOW_OPPOSITE_SIDE", "false").lower() == "true",
        )

        event_bus = None
        try:
            event_bus = self.container.resolve("IEventBus")
        except Exception:
            logger.warning("PortfolioGovernorPlugin: IEventBus not found — events disabled.")

        governor = PortfolioGovernor(config=config, event_bus=event_bus)

        # Register under class type and canonical string key
        self.container.register(PortfolioGovernor, instance=governor)
        _key = "research_platform.portfolio_governor.governor.PortfolioGovernor"
        if not self.container.has(_key):
            self.container.register(_key, instance=governor)
        # Short alias for easy resolution from plugin.py
        if not self.container.has("PortfolioGovernor"):
            self.container.register("PortfolioGovernor", instance=governor)

        logger.info(
            "PortfolioGovernorPlugin: initialized "
            "(max_pos=%d, cooldown=%.0fs, exposure=%.0f%%)",
            config.max_open_positions,
            config.default_cooldown_seconds,
            config.max_portfolio_exposure_pct * 100,
        )

    def shutdown(self) -> None:
        """No persistent resources to clean up."""

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
