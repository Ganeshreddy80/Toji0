"""Monitoring status tracker capturing realized PnL, latency, and drawdown boundaries.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from research_platform.strategy_lifecycle.interfaces import IStrategyRepository
from research_platform.strategy_lifecycle.models import LifecycleStage, MonitoringStatus

logger = logging.getLogger(__name__)


class StrategyMonitor:
    """Tracks latency, drawdown limits, heartbeats, and updates operational health states."""

    def __init__(self, repository: IStrategyRepository) -> None:
        self._repo = repository

    def submit_heartbeat(self, strategy_id: str, version_id: str, latency_ms: float, pnl: float, drawdown: float) -> MonitoringStatus:
        """Process heartbeat update and evaluate risk parameters."""
        strategy = self._repo.get_strategy(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy '{strategy_id}' not found.")

        # Resolve risk limit from the active version profile
        version = self._repo.get_version(version_id)
        max_drawdown_limit = 1.0  # Default to 100% if not specified
        if version and version.risk_profile:
            max_drawdown_limit = version.risk_profile.get("max_drawdown", 1.0)

        active_alerts = []
        health = "HEALTHY"

        # Check drawdown boundary breach
        if drawdown >= max_drawdown_limit:
            health = "UNHEALTHY"
            alert_msg = f"CRITICAL: Drawdown {drawdown:.2%} exceeded maximum allowed limit {max_drawdown_limit:.2%}"
            active_alerts.append(alert_msg)
            logger.warning(alert_msg)

            # Auto-halt: Transition strategy to PAUSED
            if strategy.current_stage in (LifecycleStage.CANARY, LifecycleStage.LIVE, LifecycleStage.MONITORING):
                logger.warning("Auto-halting strategy '%s' due to drawdown limit violation.", strategy_id)
                updated = strategy.model_copy(update={"current_stage": LifecycleStage.PAUSED})
                self._repo.save_strategy(updated)

        status = MonitoringStatus(
            status_id=f"mon-{uuid.uuid4().hex[:8]}",
            strategy_id=strategy_id,
            version_id=version_id,
            health=health,
            latency_ms=latency_ms,
            pnl=pnl,
            drawdown=drawdown,
            heartbeat_received_at=datetime.now(timezone.utc),
            active_alerts=active_alerts
        )
        self._repo.save_monitoring_status(status)
        return status
