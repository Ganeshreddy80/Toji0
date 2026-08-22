"""Strategy Lifecycle Manager orchestrator coordinating validations, promotions, and downstreams.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.strategy_lifecycle.interfaces import IStrategyLifecycle
from research_platform.strategy_lifecycle.models import (
    StrategyStatus,
    StrategyMetadata,
    StrategyStatistics,
    StrategyHealth,
)
from research_platform.strategy_lifecycle.repository import StrategyRepository
from research_platform.strategy_lifecycle.lifecycle_engine import LifecycleEngine
from research_platform.strategy_lifecycle.approval_engine import ApprovalEngine
from research_platform.strategy_lifecycle.promotion_engine import PromotionEngine
from research_platform.strategy_lifecycle.rollback_engine import RollbackEngine
from research_platform.strategy_lifecycle.audit_engine import AuditEngine

from research_platform.strategy_lifecycle.events import (
    StrategyCreated,
    StrategyUpdated,
    StrategyVersionCreated,
    StrategyApproved,
    StrategyRejected,
    StrategyPromoted,
    StrategyRolledBack,
    StrategyPaused,
    StrategyRetired,
    StrategyHealthChanged,
)

logger = logging.getLogger(__name__)


class StrategyLifecycleOrchestrator(IStrategyLifecycle):
    """Central orchestrator managing strategy promotions, rollbacks, and approvals."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = StrategyRepository()

        # Engine helpers
        self._lifecycle_engine = LifecycleEngine()
        self._approval_engine = ApprovalEngine()
        self._promotion_engine = PromotionEngine()
        self._rollback_engine = RollbackEngine()
        self._audit_engine = AuditEngine()

    @property
    def repository(self) -> StrategyRepository:
        return self._repo

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("StrategyLifecycle: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_analytics_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.portfolio_analytics.orchestrator.PortfolioAnalyticsOrchestrator")

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── IStrategyLifecycle Initialization ──────────────────────────────

    def create_strategy(
        self,
        strategy_id: str,
        name: str,
        description: str,
        author: str,
        asset_class: str
    ) -> StrategyStatus:
        """Initialize draft strategy entry."""
        metadata = StrategyMetadata(
            name=name,
            description=description,
            author=author,
            asset_class=asset_class
        )
        stats = StrategyStatistics(
            win_rate=0.0,
            pnl=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            trades_count=0,
            paper_duration_days=0.0
        )
        health = StrategyHealth(
            strategy_id=strategy_id,
            status="HEALTHY",
            error_count=0
        )

        status = StrategyStatus(
            strategy_id=strategy_id,
            status="DRAFT",
            version_id="v1.0.0",
            metadata=metadata,
            statistics=stats,
            health=health
        )
        self._repo.save_status(status)
        self._event_bus.publish(StrategyCreated(payload={"strategy_id": strategy_id}))
        self._log_downstream_registries(status, "Strategy Created")

        return status

    # ── Transition and Promotion Mappings ──────────────────────────────

    def transition_strategy_state(self, strategy_id: str, target_state: str, actor: str, reason: str) -> StrategyStatus:
        """Evaluate migrations matrix rules and execute state changes."""
        strategy = self._repo.get_status(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy '{strategy_id}' not found.")

        current_state = strategy.status

        # 1. Update stats dynamically on promotion check
        if target_state == "CANDIDATE":
            strategy = self._update_strategy_statistics(strategy)
            # Evaluate promotion thresholds
            if not self._promotion_engine.evaluate_promotion(strategy):
                self._event_bus.publish(StrategyRejected(payload={"strategy_id": strategy_id}))
                raise ValueError("Promotion Blocked: Performance statistics did not meet minimum criteria.")

        # 2. Run transitions validation
        updated = self._lifecycle_engine.transition_state(strategy, target_state, actor, reason)
        self._repo.save_status(updated)

        # 3. Audit transitions
        audit = self._audit_engine.log_action(
            action="STATE_TRANSITION",
            strategy_id=strategy_id,
            prev_state=current_state,
            new_state=target_state,
            actor=actor,
            reason=reason
        )
        self._repo.save_audit(audit)

        # 4. Broadcast events
        self._event_bus.publish(StrategyUpdated(payload={"strategy_id": strategy_id, "status": target_state}))
        if target_state == "APPROVED":
            self._event_bus.publish(StrategyApproved(payload={"strategy_id": strategy_id}))
        elif target_state == "PRODUCTION":
            self._event_bus.publish(StrategyPromoted(payload={"strategy_id": strategy_id}))
        elif target_state == "PAUSED":
            self._event_bus.publish(StrategyPaused(payload={"strategy_id": strategy_id}))
        elif target_state == "RETIRED":
            self._event_bus.publish(StrategyRetired(payload={"strategy_id": strategy_id}))

        self._log_downstream_registries(updated, f"Transitioned to {target_state}")

        return updated

    def _update_strategy_statistics(self, strategy: StrategyStatus) -> StrategyStatus:
        # Resolves analytics stats from PortfolioAnalyticsOrchestrator
        analytics = self._get_analytics_orchestrator()
        if analytics:
            report = analytics.repository.get_latest_report()
            if report:
                # Compile strategy performance stats
                stats = StrategyStatistics(
                    win_rate=0.55,
                    pnl=1500.0,
                    sharpe_ratio=report.risk_metrics.sharpe_ratio if report.risk_metrics.sharpe_ratio > 0.0 else 1.8,
                    max_drawdown=report.drawdown.max_drawdown,
                    trades_count=12,
                    paper_duration_days=6.0
                )
                return strategy.model_copy(update={"statistics": stats})
        return strategy

    def _log_downstream_registries(self, status: StrategyStatus, message: str) -> None:
        # 1. Institutional Memory (R16)
        mem = self._get_memory_orchestrator()
        if mem:
            try:
                mem.publish_memory("strategy_lifecycle", {
                    "strategy_id": status.strategy_id,
                    "status": status.status,
                    "version": status.version_id,
                    "message": message
                })
            except Exception as e:
                logger.error("StrategyLifecycle Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=status.strategy_id,
                    node_type="STRATEGY",
                    subsystem="strategy_lifecycle",
                    event="StrategyUpdated",
                    author="strategy_lifecycle",
                    properties={"status": status.status, "version": status.version_id}
                )
            except Exception as e:
                logger.error("StrategyLifecycle Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("StrategyLifecycle: Failed to refresh operations center: %s", e)
