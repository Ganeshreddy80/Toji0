"""Orchestrator compiling and exporting dashboard snapshots.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.paper_dashboard.interfaces import IPaperDashboardOrchestrator
from research_platform.paper_dashboard.models import ConsoleSessionSummary
from research_platform.paper_dashboard.repository import PaperDashboardRepository
from research_platform.paper_dashboard.events import PaperDashboardRefreshed

logger = logging.getLogger(__name__)


class PaperDashboardOrchestrator(IPaperDashboardOrchestrator):
    """Coordinates snapshot compilation and triggers notifications."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = PaperDashboardRepository()

    @property
    def repository(self) -> PaperDashboardRepository:
        return self._repo

    # ── Orchestrator Resolution Helpers ──────────────────────────────

    @property
    def paper_trading(self) -> Any:
        p_key = "research_platform.paper_trading.orchestrator.PaperTradingOrchestrator"
        if self._container and self._container.has(p_key):
            return self._container.resolve(p_key)
        raise RuntimeError("PaperTradingOrchestrator not registered in DI container.")

    @property
    def paper_market(self) -> Any:
        m_key = "research_platform.paper_market.orchestrator.PaperMarketOrchestrator"
        if self._container and self._container.has(m_key):
            return self._container.resolve(m_key)
        raise RuntimeError("PaperMarketOrchestrator not registered in DI container.")

    # ── Orchestrator Actions ──────────────────────────────────────────

    def refresh_dashboard(self) -> ConsoleSessionSummary:
        """Fetch current accounts, exposures, drawdowns and router modes."""
        trading_orch = self.paper_trading
        market_orch = self.paper_market

        active_sess = trading_orch.active_session
        routing_mode = market_orch.execution_router.mode

        if active_sess:
            acc = active_sess.account
            summary = ConsoleSessionSummary(
                account_id=acc.account_id,
                equity=acc.equity,
                cash=acc.cash,
                realized_pnl=acc.realized_pnl,
                unrealized_pnl=acc.unrealized_pnl,
                drawdown=acc.drawdown,
                routing_mode=routing_mode,
                is_session_active=True,
                last_refresh_time=datetime.now(timezone.utc)
            )
        else:
            summary = ConsoleSessionSummary(
                account_id="N/A",
                equity=0.0,
                cash=0.0,
                realized_pnl=0.0,
                unrealized_pnl=0.0,
                drawdown=0.0,
                routing_mode=routing_mode,
                is_session_active=False,
                last_refresh_time=datetime.now(timezone.utc)
            )

        self._repo.save_summary(summary)
        
        # Publish notification event
        self._event_bus.publish(PaperDashboardRefreshed(payload={
            "account_id": summary.account_id,
            "equity": summary.equity
        }))

        return summary
