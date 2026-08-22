"""Portfolio Construction orchestrator coordinating weights allocations, sizes, exposure limits, and rebalances.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.portfolio_construction.models import (
    PortfolioAllocation,
    RebalanceOrder,
    CorrelationMatrix,
)
from research_platform.portfolio_construction.repository import PortfolioConstructionRepository
from research_platform.portfolio_construction.allocation_engine import AllocationEngine
from research_platform.portfolio_construction.position_sizer import PositionSizer
from research_platform.portfolio_construction.risk_parity import RiskParityEngine
from research_platform.portfolio_construction.kelly_engine import KellyEngine
from research_platform.portfolio_construction.volatility_targeting import VolatilityTargetingEngine
from research_platform.portfolio_construction.correlation_engine import CorrelationEngine
from research_platform.portfolio_construction.exposure_engine import ExposureEngine
from research_platform.portfolio_construction.rebalancer import Rebalancer
from research_platform.portfolio_construction.events import AllocationRebalanced

logger = logging.getLogger(__name__)


class PortfolioConstructionOrchestrator:
    """Central orchestrator managing capital allocations and leverage targeting."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = PortfolioConstructionRepository()
        self._allocation_engine = AllocationEngine()
        self._sizer = PositionSizer()
        self._risk_parity = RiskParityEngine()
        self._kelly = KellyEngine()
        self._vol_targeting = VolatilityTargetingEngine()
        self._correlation = CorrelationEngine()
        self._exposure = ExposureEngine()
        self._rebalancer = Rebalancer()

    @property
    def repository(self) -> PortfolioConstructionRepository:
        return self._repo

    @property
    def correlation_engine(self) -> CorrelationEngine:
        return self._correlation

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("PortfolioConstruction: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── Domain Events Subscriptions ──────────────────────────────────

    def start_construction(self) -> None:
        """Start listening to Trade Journal events to run calculations."""
        self._event_bus.subscribe("system.trade_journal_created", self._handle_journal_event)
        self._subscribed = True
        logger.info("Portfolio Construction: Subscribed to system.trade_journal_created events.")

    def stop_construction(self) -> None:
        """Unsubscribe from the event stream."""
        if getattr(self, "_subscribed", False):
            try:
                self._event_bus.unsubscribe("system.trade_journal_created", self._handle_journal_event)
            except Exception as e:
                logger.error("Portfolio Construction: Failed to unsubscribe: %s", e)
            self._subscribed = False
        logger.info("Portfolio Construction: Stopped construction subscription.")

    def _handle_journal_event(self, event: Any) -> None:
        try:
            # Dynamically recalculate correlation on new trade journals
            assets = ["BTCUSDT", "ETHUSDT"]
            corr = self._correlation.calculate_correlation(assets)
            self._repo.save_correlation_matrix(corr)
            logger.info("Portfolio Construction: Automatically updated asset correlation matrix on trade: %s", corr)
        except Exception as e:
            logger.error("Portfolio Construction: Failed to run allocation on trade: %s", e)

    # ── Actions ──────────────────────────────────────────────────────

    def create_allocation(self, allocation_id: str, weights: Dict[str, float]) -> PortfolioAllocation:
        alloc = self._allocation_engine.initiate_allocation(allocation_id, weights)
        self._repo.save_allocation(alloc)
        
        self._event_bus.publish(AllocationRebalanced(payload={"allocation_id": allocation_id}))
        self._log_downstream_registries(allocation_id, "PORTFOLIO_ALLOCATION", f"Allocation Created: assets={list(weights.keys())}")
        return alloc

    def size_positions_equally(self, assets: List[str]) -> Dict[str, float]:
        return self._sizer.size_equally(assets)

    def calculate_risk_parity(self, assets: List[str], volatilities: Dict[str, float]) -> Dict[str, float]:
        return self._risk_parity.calculate_risk_parity(assets, volatilities)

    def calculate_kelly_fraction(
        self,
        assets: List[str],
        win_rates: Dict[str, float],
        win_loss_ratios: Dict[str, float]
    ) -> Dict[str, float]:
        return self._kelly.calculate_kelly_fraction(assets, win_rates, win_loss_ratios)

    def scale_allocation(
        self,
        weights: Dict[str, float],
        realized_volatility: float,
        target_volatility: float = 0.15
    ) -> Dict[str, float]:
        return self._vol_targeting.scale_to_target(weights, realized_volatility, target_volatility)

    def limit_exposure(self, weights: Dict[str, float], max_asset_limit: float = 0.25) -> Dict[str, float]:
        return self._exposure.check_exposure_limits(weights, max_asset_limit)

    def compile_rebalance_orders(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float]
    ) -> List[RebalanceOrder]:
        return self._rebalancer.compile_rebalance(current_weights, target_weights)

    def _log_downstream_registries(self, ref_id: str, element_type: str, message: str) -> None:
        # 1. Institutional Memory (R16)
        mem = self._get_memory_orchestrator()
        if mem:
            try:
                mem.publish_memory("observability", {
                    "ref_id": ref_id,
                    "type": element_type,
                    "message": message
                })
            except Exception as e:
                logger.error("PortfolioConstruction Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=ref_id,
                    node_type=element_type,
                    subsystem="portfolio_construction",
                    event="PortfolioUpdated",
                    author="portfolio_construction",
                    properties={"message": message}
                )
            except Exception as e:
                logger.error("PortfolioConstruction Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("PortfolioConstruction: Failed to refresh operations center: %s", e)
