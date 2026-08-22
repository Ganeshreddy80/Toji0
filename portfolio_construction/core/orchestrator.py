"""Portfolio Construction Orchestrator managing pipeline execution and event dispatching."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import uuid
from typing import Any, Dict, List, Optional

from portfolio_construction.core.enums import OptimizationObjective, PortfolioDecision
from portfolio_construction.core.events import (
    PortfolioConstructionApproved,
    PortfolioConstructionRejected,
    PortfolioGenerated,
    PortfolioUpdated,
)
from portfolio_construction.core.exceptions import OrchestratorError
from portfolio_construction.core.interfaces import (
    IPortfolioConstructionEngine,
    IPortfolioConstructionRepository,
    IPortfolioConstructionStateStore,
)
from portfolio_construction.core.models import (
    PortfolioCandidate,
    PortfolioConstraintConfig,
    PortfolioConstructionSnapshot,
    PortfolioConstructionState,
    TargetPortfolio,
)
from portfolio_construction.analysis.construction_engine import PortfolioConstructionEngine
from strategy.core.models import StrategySignal
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class PortfolioConstructionOrchestrator:
    """Coordinates portfolio construction, state storage, persistence, and event bus broadcasts."""

    def __init__(self) -> None:
        self._engine: IPortfolioConstructionEngine | None = None
        self._state_store: IPortfolioConstructionStateStore | None = None
        self._repository: IPortfolioConstructionRepository | None = None
        self._event_bus: IEventBus | None = None
        self._container: IContainer | None = None

    def initialize(
        self,
        engine: IPortfolioConstructionEngine,
        state_store: IPortfolioConstructionStateStore,
        repository: IPortfolioConstructionRepository,
        event_bus: IEventBus | None = None,
        container: IContainer | None = None,
    ) -> None:
        """Inject dependencies into the orchestrator."""
        self._engine = engine
        self._state_store = state_store
        self._repository = repository
        self._event_bus = event_bus
        self._container = container

        if container is not None and self._event_bus is None and container.has(IEventBus):
            self._event_bus = container.resolve(IEventBus)

    def process_signals(
        self,
        strategy_signals: List[StrategySignal],
        market_states: Optional[Dict[str, Any]] = None,
        correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        config: Optional[PortfolioConstraintConfig] = None,
        objective: OptimizationObjective = OptimizationObjective.CONFIDENCE_WEIGHTED,
        symbol: str = "PORTFOLIO",
    ) -> PortfolioConstructionState:
        """
        Run portfolio construction pipeline over input strategy signals.
        Fails closed on any exception, returning a safe HOLD state.
        """
        if not self._engine or not self._state_store or not self._repository:
            raise OrchestratorError("PortfolioConstructionOrchestrator is not initialized.")

        try:
            # 1. Convert StrategySignal inputs to PortfolioCandidate objects
            candidates: List[PortfolioCandidate] = []
            for sig in strategy_signals:
                if sig is not None and getattr(sig, "decision", None) and str(sig.decision.value if hasattr(sig.decision, "value") else sig.decision) != "WAIT":
                    candidates.append(
                        PortfolioCandidate(
                            signal_id=sig.signal_id,
                            symbol=sig.symbol,
                            timeframe=sig.timeframe,
                            direction=str(sig.direction.value if hasattr(sig.direction, "value") else sig.direction),
                            strategy_type=str(sig.strategy_type.value if hasattr(sig.strategy_type, "value") else sig.strategy_type),
                            confidence=sig.confidence,
                            sector="GENERAL",
                            expected_return=sig.confidence,
                            volatility=0.20,
                        )
                    )

            # 2. Construct target portfolio
            target_portfolio = self._engine.construct_portfolio(
                candidates=candidates,
                correlation_matrix=correlation_matrix,
                config=config,
                objective=objective,
            )

            # 3. Update state store
            state_update = PortfolioConstructionState(
                symbol=symbol,
                active_portfolio=target_portfolio,
                updated_at=datetime.now(timezone.utc),
            )
            snapshot = self._state_store.update_state(state_update)

            # 4. Save to repository
            self._repository.save_snapshot(snapshot)

            # 5. Dispatch events
            self._dispatch_events(snapshot.state)

            return snapshot.state

        except Exception as e:
            logger.error("PortfolioConstructionOrchestrator: Runtime error: %s. Failing closed to HOLD state.", e, exc_info=True)
            fail_portfolio = TargetPortfolio(
                portfolio_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                decision=PortfolioDecision.HOLD,
                allocations={},
                target_weights={},
                total_weight=0.0,
                active_positions_count=0,
                confidence=0.0,
                reasoning=f"Fail-Closed: Orchestrator runtime exception: {e}",
                rejected_candidates=[],
            )
            try:
                fail_state_update = PortfolioConstructionState(
                    symbol=symbol,
                    active_portfolio=fail_portfolio,
                    updated_at=datetime.now(timezone.utc),
                )
                fail_snapshot = self._state_store.update_state(fail_state_update)
                self._repository.save_snapshot(fail_snapshot)
                self._dispatch_events(fail_snapshot.state)
                return fail_snapshot.state
            except Exception as store_err:
                logger.error("PortfolioConstructionOrchestrator: Failed to persist fail-closed state: %s", store_err)
                return PortfolioConstructionState(
                    symbol=symbol,
                    active_portfolio=fail_portfolio,
                    updated_at=datetime.now(timezone.utc),
                )

    def _dispatch_events(self, state: PortfolioConstructionState) -> None:
        """Publish deterministic transition and allocation events to EventBus."""
        if self._event_bus is None:
            return

        source = "portfolio_construction.orchestrator"
        state_json = state.model_dump(mode="json")
        target = state.active_portfolio
        target_json = target.model_dump(mode="json")

        # 1. Always publish PortfolioUpdated & PortfolioGenerated
        self._event_bus.publish(PortfolioUpdated(source=source, payload={"state": state_json}))
        self._event_bus.publish(PortfolioGenerated(source=source, payload={"state": state_json, "target_portfolio": target_json}))

        # 2. Check approval vs rejection
        if target.decision != PortfolioDecision.HOLD and target.target_weights:
            self._event_bus.publish(PortfolioConstructionApproved(source=source, payload={"target_portfolio": target_json}))
        else:
            self._event_bus.publish(PortfolioConstructionRejected(source=source, payload={"reason": target.reasoning, "target_portfolio": target_json}))

    @property
    def engine(self) -> IPortfolioConstructionEngine | None:
        return self._engine

    @property
    def state_store(self) -> IPortfolioConstructionStateStore | None:
        return self._state_store

    @property
    def repository(self) -> IPortfolioConstructionRepository | None:
        return self._repository
