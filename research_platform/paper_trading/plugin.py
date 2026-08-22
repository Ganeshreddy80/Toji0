"""Paper trading plugin registration.
"""

from __future__ import annotations

from typing import Any
from research_platform.paper_trading.orchestrator import PaperTradingOrchestrator


class PaperTradingPlugin:
    """Hooks the paper trading components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register orchestrator mappings."""
        event_bus = self.container.resolve("IEventBus")
        
        orchestrator = PaperTradingOrchestrator(event_bus, container=self.container)
        self.container.register(PaperTradingOrchestrator, instance=orchestrator)
        # Also register by full string key so PaperExecutionRouter can resolve it
        _full_key = "research_platform.paper_trading.orchestrator.PaperTradingOrchestrator"
        if not self.container.has(_full_key):
            self.container.register(_full_key, instance=orchestrator)

        # Auto-start a default paper session so incoming signals can be filled immediately
        import logging as _log
        _logger = _log.getLogger(__name__)
        try:
            orchestrator.start_paper_session(
                account_id="default_paper_account",
                initial_balance=100_000.0
            )
            _logger.info("PaperTradingPlugin: default paper session started (balance=100,000 USDT).")
        except Exception as exc:
            _logger.error("PaperTradingPlugin: failed to auto-start paper session: %s", exc)

    def shutdown(self) -> None:
        """Cleanup resources."""
        pass

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
