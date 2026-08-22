"""Execution Engine Orchestrator coordinating rate limiting checks, exchange submits, and reconciliations.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from toji_platform.core.event_bus import IEventBus

from research_platform.execution_engine.events import (
    ExchangeConnected,
    FillReceived,
    OrderAcknowledged,
    OrderSubmitted,
    ReconciliationCompleted
)
from research_platform.execution_engine.health import HealthMonitor
from research_platform.execution_engine.models import ExecutionReport
from research_platform.execution_engine.rate_limiter import TokenBucketRateLimiter
from research_platform.execution_engine.reconciliation import StateReconciler
from research_platform.execution_engine.repository import ExecutionRepository
from research_platform.execution_engine.router import ExchangeRouter
from research_platform.execution_engine.sync import StateSynchronizer
from research_platform.oms.models import Order

logger = logging.getLogger(__name__)


class ExecutionEngineOrchestrator:
    """Coordinates order adapters, enforcing rate limit buckets and updating health profiles."""

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._repo = ExecutionRepository()
        self._router = ExchangeRouter()
        self._rate_limiter = TokenBucketRateLimiter(capacity=10.0, refill_rate=2.0)
        self._health = HealthMonitor()

    @property
    def repository(self) -> ExecutionRepository:
        return self._repo

    def execute_order(self, order: Order, exchange: str) -> ExecutionReport:
        """Submit order to correct exchange endpoint, enforcing rate limit rules."""
        import os
        if os.getenv("TRADING_MODE") == "paper":
            raise PermissionError("Safety Breach: Real exchange orders are blocked when TRADING_MODE=paper!")

        self._event_bus.publish(OrderSubmitted(payload={"order_id": order.order_id}))

        # 1. Select Exchange Adapter
        adapter = self._router.get_adapter(exchange)
        
        # 2. Connect adapter
        adapter.connect()
        self._event_bus.publish(ExchangeConnected(payload={"exchange": exchange}))

        # 3. Apply Rate Limiting
        if not self._rate_limiter.allow_request():
            logger.warning("Execution throttled: Token Bucket rate limit exceeded for %s", exchange)
            raise ValueError(f"Rate limit exceeded for exchange {exchange}")

        # 4. Submit Order (with execution latency log)
        start_time = time.time()
        try:
            report = adapter.submit_order(order.request)
            success = True
        except Exception as e:
            success = False
            logger.error("Order submission failed: %s", e)
            raise

        latency_ms = (time.time() - start_time) * 1000.0
        self._health.record_request(latency_ms, success)

        self._repo.save_report(report)
        self._event_bus.publish(OrderAcknowledged(payload={"order_id": order.order_id}))
        self._event_bus.publish(FillReceived(payload={"order_id": order.order_id}))

        # 5. Synchronize State
        synchronizer = StateSynchronizer(adapter)
        synchronizer.sync_state()

        # 6. Reconcile states
        rec_log = StateReconciler.reconcile([order], synchronizer.positions)
        self._repo.save_reconciliation(rec_log)
        self._event_bus.publish(ReconciliationCompleted(payload={"reconciled": rec_log.reconciled}))

        logger.info("EMS successfully executed order %s on exchange %s", order.order_id, exchange)
        return report
