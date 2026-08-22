"""Stress Testing orchestrator coordinating scenarios creation, execution shocks, and recovery planning.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.stress_testing.models import (
    StressScenario,
    StressRun,
    RecoveryPlan,
)
from research_platform.stress_testing.repository import StressTestingRepository
from research_platform.stress_testing.scenario_engine import ScenarioEngine
from research_platform.stress_testing.volatility_engine import VolatilityEngine
from research_platform.stress_testing.recovery_engine import RecoveryEngine
from research_platform.stress_testing.events import StressScenarioRun

logger = logging.getLogger(__name__)


class StressTestingOrchestrator:
    """Central orchestrator managing historical and synthetic shocks."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = StressTestingRepository()
        self._scenario = ScenarioEngine()
        self._volatility = VolatilityEngine()
        self._recovery = RecoveryEngine()

    @property
    def repository(self) -> StressTestingRepository:
        return self._repo

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("StressTesting: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── Actions ──────────────────────────────────────────────────────

    def create_scenario(
        self,
        scenario_id: str,
        name: str,
        shock_type: str,
        magnitude: float
    ) -> StressScenario:
        scen = self._scenario.create_scenario(scenario_id, name, shock_type, magnitude)
        self._repo.save_scenario(scen)
        return scen

    def run_stress_test(self, run_id: str, scenario_id: str, initial_value: float) -> StressRun:
        scen = self._repo.get_scenario(scenario_id)
        if not scen:
            raise ValueError(f"Scenario '{scenario_id}' not found.")

        # Simulate shocks based on type
        if scen.shock_type == "VOL_SHOCK":
            shocked = self._volatility.shock_portfolio(initial_value, scen.magnitude)
        else:
            # Multiplicative drawdown
            shocked = max(0.0, initial_value * (1.0 - scen.magnitude))

        drawdown = 0.0
        if initial_value > 0.0:
            drawdown = (initial_value - shocked) / initial_value

        run = StressRun(
            run_id=run_id,
            scenario_id=scenario_id,
            initial_value=initial_value,
            shocked_value=shocked,
            drawdown_pct=drawdown
        )
        self._repo.save_run(run)
        
        self._event_bus.publish(StressScenarioRun(payload={"run_id": run_id}))
        self._log_downstream_registries(run_id, "STRESS_RUN", f"Stress Run Executed: drawdown={drawdown}")
        return run

    def compile_recovery_plan(self, run_id: str, drawdown_pct: float) -> RecoveryPlan:
        plan = self._recovery.compile_recovery_plan(run_id, drawdown_pct)
        self._repo.save_recovery(plan)
        return plan

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
                logger.error("StressTesting Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=ref_id,
                    node_type=element_type,
                    subsystem="stress_testing",
                    event="StressUpdated",
                    author="stress_testing",
                    properties={"message": message}
                )
            except Exception as e:
                logger.error("StressTesting Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("StressTesting: Failed to refresh operations center: %s", e)
