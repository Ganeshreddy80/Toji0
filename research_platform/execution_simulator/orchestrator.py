"""Execution Simulator orchestrator coordinating matching models, latency simulations, market impacts, slippages.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.execution_simulator.models import SimulatedExecution
from research_platform.execution_simulator.repository import ExecutionSimulatorRepository
from research_platform.execution_simulator.execution_engine import ExecutionEngine
from research_platform.execution_simulator.latency_engine import LatencyEngine
from research_platform.execution_simulator.market_impact import MarketImpactEngine
from research_platform.execution_simulator.queue_model import QueueModel
from research_platform.execution_simulator.vwap_engine import VwapEngine
from research_platform.execution_simulator.twap_engine import TwapEngine
from research_platform.execution_simulator.events import (
    OrderSimulationStarted,
    OrderSimulationCompleted,
)

logger = logging.getLogger(__name__)


class ExecutionSimulatorOrchestrator:
    """Central orchestrator managing execution simulations."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = ExecutionSimulatorRepository()
        self._engine = ExecutionEngine()
        self._latency = LatencyEngine()
        self._market_impact = MarketImpactEngine()
        self._queue = QueueModel()
        self._vwap = VwapEngine()
        self._twap = TwapEngine()

    @property
    def repository(self) -> ExecutionSimulatorRepository:
        return self._repo

    @property
    def latency_engine(self) -> LatencyEngine:
        return self._latency

    @property
    def market_impact_engine(self) -> MarketImpactEngine:
        return self._market_impact

    @property
    def queue_model(self) -> QueueModel:
        return self._queue

    @property
    def vwap_engine(self) -> VwapEngine:
        return self._vwap

    @property
    def twap_engine(self) -> TwapEngine:
        return self._twap

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("ExecutionSimulator: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── Actions ──────────────────────────────────────────────────────

    def simulate_execution(
        self,
        order_id: str,
        symbol: str,
        quantity: float,
        price: float,
        order_type: str,
        side: str
    ) -> SimulatedExecution:
        self._event_bus.publish(OrderSimulationStarted(payload={"order_id": order_id}))
        
        # Simulate network latency delay
        self._latency.simulate_delay("PRODUCTION")

        exec_report = self._engine.simulate_order_execution(order_id, symbol, quantity, price, order_type, side)
        self._repo.save_execution(exec_report)
        
        self._event_bus.publish(OrderSimulationCompleted(payload={"execution_id": exec_report.execution_id}))
        self._log_downstream_registries(exec_report.execution_id, "SIMULATED_EXECUTION", f"Order Executed: average_price={exec_report.average_price}")
        return exec_report

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
                logger.error("ExecutionSimulator Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=ref_id,
                    node_type=element_type,
                    subsystem="execution_simulator",
                    event="ExecutionUpdated",
                    author="execution_simulator",
                    properties={"message": message}
                )
            except Exception as e:
                logger.error("ExecutionSimulator Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("ExecutionSimulator: Failed to refresh operations center: %s", e)
