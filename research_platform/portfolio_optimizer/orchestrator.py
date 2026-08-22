"""Portfolio optimizer orchestrator coordinating correlation matrices, weights solver, rebalancing, and external subsystems.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.portfolio_optimizer.interfaces import IPortfolioOptimizerOrchestrator
from research_platform.portfolio_optimizer.models import (
    CorrelationMatrix,
    OptimizerResult,
    PortfolioAllocation,
    RiskBudget,
)
from research_platform.portfolio_optimizer.repository import PortfolioOptimizerRepository
from research_platform.portfolio_optimizer.correlation import CorrelationEngine
from research_platform.portfolio_optimizer.risk_budgeting import RiskBudgeter
from research_platform.portfolio_optimizer.optimizer import PortfolioOptimizationEngine
from research_platform.portfolio_optimizer.balancer import ExposureBalancer
from research_platform.portfolio_optimizer.events import (
    AllocationAdjusted,
    ExposureRebalanced,
    PortfolioOptimizationStarted,
    PortfolioOptimized,
    RiskBudgetBreached,
)

logger = logging.getLogger(__name__)


class PortfolioOptimizerOrchestrator(IPortfolioOptimizerOrchestrator):
    """Central orchestrator managing rebalance workflows and publishing weights maps."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = PortfolioOptimizerRepository()

        # Engines
        self._correlation_engine = CorrelationEngine()
        self._risk_budgeter = RiskBudgeter()
        self._optimizer = PortfolioOptimizationEngine()
        self._balancer = ExposureBalancer()

    @property
    def repository(self) -> PortfolioOptimizerRepository:
        return self._repo

    # ── Downstream Integration Helpers ───────────────────────────────

    def _get_memory_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator"):
            return self._container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
        return None

    def _get_kg_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator"):
            return self._container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
        return None

    def _publish_memory_record(self, record: PortfolioAllocation) -> None:
        mem_orch = self._get_memory_orchestrator()
        if not mem_orch:
            return
        try:
            mem_orch.publish_memory("portfolio_allocations", record)
        except Exception as e:
            logger.error("Failed to publish to institutional memory: %s", e)

    def _update_knowledge_graph(self, record: PortfolioAllocation, correlation: Optional[CorrelationMatrix] = None) -> None:
        kg_orch = self._get_kg_orchestrator()
        if not kg_orch:
            return
        try:
            # Register Allocation Node
            kg_orch.register_node(
                node_id=record.allocation_id,
                node_type="PORTFOLIO_ALLOCATION",
                subsystem="portfolio_optimizer",
                event="PortfolioOptimized",
                author="system",
                properties={"net_exposure": record.net_exposure, "gross_exposure": record.gross_exposure}
            )

            # Register connection links for each weighted symbol
            for sym, weight in record.weights.items():
                kg_orch.register_node(
                    node_id=sym,
                    node_type="ASSET",
                    subsystem="portfolio_optimizer",
                    event="PortfolioOptimized",
                    author="system",
                    properties={"weight": weight}
                )
                kg_orch.link_nodes(
                    source_id=record.allocation_id,
                    target_id=sym,
                    relationship_type="uses",
                    subsystem="portfolio_optimizer"
                )
        except Exception as e:
            logger.error("Failed to update knowledge graph: %s", e)

    # ── Orchestrator Actions ──────────────────────────────────────────

    def run_optimization(
        self,
        returns_data: Dict[str, List[float]],
        limits: Dict[str, float] = None,
        risk_tolerance: float = 0.5,
        concentration_limit: float = 0.4
    ) -> PortfolioAllocation:
        """Run complete rebalance workflow, balance exposures, and track results."""
        self._event_bus.publish(PortfolioOptimizationStarted(payload={}))
        symbols = sorted(list(returns_data.keys()))

        # 1. Compute correlations
        corr = self._correlation_engine.calculate_correlation(returns_data)
        self._repo.save_correlation(corr)

        # 2. Run optimizer solver
        res = self._optimizer.optimize_portfolio(symbols, returns_data, target_risk=risk_tolerance)
        self._repo.save_optimizer_result(res)
        self._event_bus.publish(PortfolioOptimized(payload={"sharpe": res.sharpe_ratio}))

        # 3. Covariance mapping for risk budgeting
        _, covariance = self._optimizer._compute_covariance(returns_data, symbols)

        # 4. Check risk budgeting limits
        if limits:
            risk_budget = self._risk_budgeter.evaluate_risk_budget(res.weights, covariance, limits)
            for sym, val in risk_budget.marginal_contributions.items():
                lim = limits.get(sym, 1.0)
                if val > lim:
                    self._event_bus.publish(RiskBudgetBreached(payload={"symbol": sym, "contribution": val, "limit": lim}))

        # 5. Exposure rebalancing
        balanced = self._balancer.balance_weights(
            res.weights,
            net_limit=1.0,
            gross_limit=1.5,
            concentration_limit=concentration_limit
        )

        # 6. Build allocation timeline record
        gross_exp = sum(abs(w) for w in balanced.values())
        net_exp = sum(balanced.values())

        allocation = PortfolioAllocation(
            allocation_id=f"alloc-{uuid.uuid4().hex[:8]}",
            weights=balanced,
            net_exposure=net_exp,
            gross_exposure=gross_exp
        )
        self._repo.save_allocation(allocation)

        # 7. Publish completion events
        self._event_bus.publish(ExposureRebalanced(payload={"gross_exposure": gross_exp, "net_exposure": net_exp}))
        self._event_bus.publish(AllocationAdjusted(payload=balanced))

        # 8. Downstream wiring
        self._publish_memory_record(allocation)
        self._update_knowledge_graph(allocation, corr)

        return allocation
