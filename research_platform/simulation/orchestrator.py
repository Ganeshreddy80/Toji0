"""Simulation orchestrator coordinating deterministic replays, order executions, and what-if stress evaluations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.simulation.interfaces import ISimulationOrchestrator
from research_platform.simulation.models import (
    ReplayConfiguration,
    ReplayMode,
    SimOrder,
    SimulationResult,
    SimTick,
    StressParameters,
)
from research_platform.simulation.repository import SimulationRepository
from research_platform.simulation.exchange import ExchangeSimulator
from research_platform.simulation.replayer import MarketReplayer
from research_platform.simulation.events import (
    FailureInjected,
    SimulationCompleted,
    SimulationStarted,
    SimOrderExecuted,
    SimTickReplayed,
)

logger = logging.getLogger(__name__)


class SimulationOrchestrator(ISimulationOrchestrator):
    """Central coordinator managing simulation environments and verification replays."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = SimulationRepository()

        # Engines
        self._exchange = ExchangeSimulator()
        self._replayer = MarketReplayer()

    @property
    def repository(self) -> SimulationRepository:
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

    def _publish_memory_record(self, category: str, record: Any) -> None:
        mem_orch = self._get_memory_orchestrator()
        if not mem_orch:
            return
        try:
            mem_orch.publish_memory(category, record)
        except Exception as e:
            logger.error("Failed to publish to institutional memory: %s", e)

    def _update_knowledge_graph(self, config: ReplayConfiguration, result: Optional[SimulationResult] = None) -> None:
        kg_orch = self._get_kg_orchestrator()
        if not kg_orch:
            return
        try:
            # Register Simulation Session Node
            kg_orch.register_node(
                node_id=config.session_id,
                node_type="SIMULATION_RUN",
                subsystem="simulation",
                event="SimulationStarted",
                author="system",
                properties={"mode": config.mode.value}
            )

            # Link Strategy nodes
            for strat_id in config.strategy_ids:
                kg_orch.register_node(
                    node_id=strat_id,
                    node_type="STRATEGY",
                    subsystem="simulation",
                    event="SimulationStarted",
                    author="system",
                    properties={"strategy_id": strat_id}
                )
                kg_orch.link_nodes(
                    source_id=config.session_id,
                    target_id=strat_id,
                    relationship_type="uses",
                    subsystem="simulation"
                )
        except Exception as e:
            logger.error("Failed to update knowledge graph: %s", e)

    # ── Orchestrator Actions ──────────────────────────────────────────

    def execute_simulation_replay(
        self,
        session_id: str,
        strategy_ids: List[str],
        mode: ReplayMode,
        start_time: datetime,
        end_time: datetime,
        ticks: List[SimTick],
        orders: List[SimOrder],
        stress_params: Optional[StressParameters] = None,
        actual_returns: Optional[List[float]] = None
    ) -> SimulationResult:
        """Run tick-by-tick simulation replay, match orders, stress test inputs, and compute replica variances."""
        stress = stress_params or StressParameters()
        config = ReplayConfiguration(
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            strategy_ids=strategy_ids,
            mode=mode,
            stress_params=stress
        )
        self._repo.save_configuration(config)
        self._event_bus.publish(SimulationStarted(payload={"session_id": session_id}))

        # Downstream
        self._publish_memory_record("simulation_configs", config)
        self._update_knowledge_graph(config)

        # 1. Stress the historical tick price feed if volatility multiplier is set
        replayed_ticks = self._replayer.replay_ticks(ticks, config)

        # 2. Iterate sequentially through ticks and match pending orders
        simulated_orders: List[SimOrder] = []
        pending_orders = list(orders)

        for tick in replayed_ticks:
            self._event_bus.publish(SimTickReplayed(payload={"timestamp": tick.timestamp.isoformat()}))
            
            still_pending = []
            for order in pending_orders:
                updated_order = self._exchange.match_order_with_stress(order, tick, stress)
                if updated_order.status == "FILLED":
                    self._repo.save_order(updated_order)
                    self._event_bus.publish(SimOrderExecuted(payload={
                        "order_id": updated_order.order_id,
                        "price": updated_order.price
                    }))
                    simulated_orders.append(updated_order)
                else:
                    still_pending.append(updated_order)
            
            pending_orders = still_pending

        # Failures inject simulated warning
        if stress.volatility_multiplier > 1.5:
            self._event_bus.publish(FailureInjected(payload={"warning": "Extreme volatility warning injected."}))

        # 3. Calculate simulated stats
        total_trades = len(simulated_orders)
        
        # Simulated PnL math: BUY opens long, SELL opens short (simple mock evaluation)
        total_pnl = 0.0
        for ord in simulated_orders:
            multiplier = -1.0 if ord.side == "BUY" else 1.0
            total_pnl += ord.quantity * ord.price * multiplier

        # 4. Calculate replica returns and variance error comparing simulated to actual returns
        # Re-construct returns from ticks
        simulated_returns = []
        if len(replayed_ticks) > 1:
            for i in range(1, len(replayed_ticks)):
                r = (replayed_ticks[i].price - replayed_ticks[i-1].price) / replayed_ticks[i-1].price
                simulated_returns.append(r)

        rep_error = 0.0
        if actual_returns and simulated_returns:
            rep_error = self._replayer.calculate_replication_error(actual_returns, simulated_returns)

        result = SimulationResult(
            session_id=session_id,
            total_trades=total_trades,
            total_pnl=total_pnl,
            max_drawdown=0.04,  # standard mock threshold
            replication_error=rep_error
        )
        self._repo.save_result(result)
        self._event_bus.publish(SimulationCompleted(payload={"session_id": session_id}))

        # Downstream result wiring
        self._publish_memory_record("simulation_results", result)

        return result
