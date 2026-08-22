"""Position Sizing Orchestrator for coordinating size calculations, persistence, and events."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from risk_engine.core.enums import RiskDecision
from position_sizing.core.enums import SizingStatus, PositionSizingMethod
from position_sizing.core.exceptions import OrchestratorError
from position_sizing.core.interfaces import (
    IPositionSizingEngine,
    IPositionSizingRepository,
    IPositionSizingStateStore,
)
from position_sizing.core.models import (
    PositionSizingState,
    PositionSizingSnapshot,
)
from position_sizing.core.events import (
    PositionSizeUpdated,
    PositionSizeCalculated,
    PositionSizeRejected,
    PositionSizeChanged,
)

logger = logging.getLogger(__name__)


class PositionSizingOrchestrator:
    """Coordinates calculating position sizing on active trade setups."""

    def __init__(self) -> None:
        self._state_store: IPositionSizingStateStore | None = None
        self._repository: IPositionSizingRepository | None = None
        self._sizing_engine: IPositionSizingEngine | None = None
        self._event_bus: IEventBus | None = None
        self._config_provider: IConfigProvider | None = None
        self._container: IContainer | None = None

    def initialize(
        self,
        state_store: IPositionSizingStateStore,
        repository: IPositionSizingRepository,
        sizing_engine: IPositionSizingEngine,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
    ) -> None:
        """Inject dependencies into the orchestrator."""
        self._state_store = state_store
        self._repository = repository
        self._sizing_engine = sizing_engine
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container

        # Resolve missing services from the DI container if available
        if container is not None:
            if self._event_bus is None and container.has(IEventBus):
                self._event_bus = container.resolve(IEventBus)
            if self._config_provider is None and container.has(IConfigProvider):
                self._config_provider = container.resolve(IConfigProvider)

    def process_context(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> PositionSizingState | None:
        """Calculate position sizing, update state store, save snapshot, and dispatch events."""
        if not self._state_store or not self._repository or not self._sizing_engine:
            raise OrchestratorError("PositionSizingOrchestrator is not initialized.")

        try:
            symbol = context.symbol
            timeframe = context.timeframe

            # 0. Early short-circuit if RiskDecision is BLOCK
            if risk_assessment.decision == RiskDecision.BLOCK:
                logger.warning("PositionSizingOrchestrator: Pipeline short-circuited due to BLOCK risk decision.")
                result = self._sizing_engine.calculate_size(context, risk_assessment, **kwargs)
                return PositionSizingState(
                    symbol=symbol,
                    timeframe=timeframe,
                    result=result,
                    updated_at=datetime.now(timezone.utc),
                )

            # 1. Compile configuration options
            config_params = {}
            if self._config_provider:
                config_params["account_balance"] = self._config_provider.get("sizing.account_balance", 100000.0)
                config_params["risk_percent"] = self._config_provider.get("sizing.risk_percent", 0.01)
                config_params["max_leverage"] = self._config_provider.get("sizing.max_leverage", 10.0)
                config_params["max_single_trade_risk_pct"] = self._config_provider.get("sizing.max_single_trade_risk_pct", 0.02)
                config_params["max_portfolio_exposure_pct"] = self._config_provider.get("sizing.max_portfolio_exposure_pct", 0.50)
                config_params["contract_size"] = self._config_provider.get("sizing.contract_size", 1.0)
                config_params["default_sizing_method"] = self._config_provider.get("sizing.default_method", "FIXED_FRACTIONAL")
                config_params["kelly_fraction"] = self._config_provider.get("sizing.kelly_fraction", "HALF")

            # Override/supplement with explicit runtime kwargs
            eval_kwargs = {**config_params, **kwargs}

            # 2. Fetch previous size if available (to check for changed events)
            previous_qty = 0.0
            prev_snapshot = self._state_store.get_snapshot(symbol)
            if prev_snapshot and timeframe in prev_snapshot.states:
                prev_state = prev_snapshot.states[timeframe]
                if prev_state.result.success and prev_state.result.position_size:
                    previous_qty = prev_state.result.position_size.quantity

            # 3. Run position sizing engine
            result = self._sizing_engine.calculate_size(context, risk_assessment, **eval_kwargs)

            # 4. Construct PositionSizingState
            state = PositionSizingState(
                symbol=symbol,
                timeframe=timeframe,
                result=result,
                updated_at=datetime.now(timezone.utc),
            )

            # 5. Initialize active snapshot if needed
            if prev_snapshot is None:
                prev_snapshot = PositionSizingSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    symbol=symbol,
                    timestamp=state.updated_at,
                    states={},
                )
                self._state_store.update_snapshot(prev_snapshot)

            # 6. Update state store
            updated_snapshot = self._state_store.update_timeframe_state(
                symbol=symbol,
                timeframe=timeframe,
                state_update=state,
            )

            # 7. Save to repository
            self._repository.save_snapshot(updated_snapshot)

            # 8. Dispatch events
            self._dispatch_events(state, previous_qty)

            return state

        except Exception as e:
            logger.error("PositionSizingOrchestrator: Sizing calculation failed: %s", e)
            raise OrchestratorError(f"Failed to process position sizing calculation: {e}") from e

    def _dispatch_events(self, state: PositionSizingState, previous_qty: float) -> None:
        """Publish updated/calculated/rejected/changed events to the event bus."""
        if not self._event_bus:
            return

        symbol = state.symbol
        timeframe = state.timeframe
        source = "position_sizing.orchestrator"
        state_json = state.model_dump(mode="json")
        result = state.result

        # 1. Publish system.position_size_updated
        self._event_bus.publish(
            PositionSizeUpdated(
                source=source,
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "state": state_json,
                },
            )
        )

        # 2. Publish success or failure events
        if result.success and result.position_size:
            # Publish system.position_size_calculated
            self._event_bus.publish(
                PositionSizeCalculated(
                    source=source,
                    payload={
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "state": state_json,
                    },
                )
            )

            # Check if quantity changed significantly (e.g. > 0.0001 difference or non-zero to zero)
            new_qty = result.position_size.quantity
            if abs(new_qty - previous_qty) > 1e-5:
                # Publish system.position_size_changed
                self._event_bus.publish(
                    PositionSizeChanged(
                        source=source,
                        payload={
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "previous_size": previous_qty,
                            "new_size": new_qty,
                        },
                    )
                )
        else:
            # Publish system.position_size_rejected
            primary_reason = result.violations[0] if result.violations else "Position sizing rejected."
            self._event_bus.publish(
                PositionSizeRejected(
                    source=source,
                    payload={
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "state": state_json,
                        "reason": primary_reason,
                    },
                )
            )
