from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import ValidationError as PydanticValidationError

from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.event_bus.events import BaseEvent

from execution_engine.core.enums import ExecutionStatus, OrderSide, OrderState, OrderType, OrderTimeInForce
from execution_engine.core.audit import ExecutionAuditRecord
from execution_engine.core.exceptions import OrchestratorError
from execution_engine.core.interfaces import (
    IExecutionEngine,
    IExecutionRepository,
    IExecutionStateStore,
)
from execution_engine.core.models import ExecutionRequest, ExecutionResult, Order
from execution_engine.core.events import (
    ExecutionRequested,
    ExecutionValidated,
    ExecutionSubmitted,
    ExecutionAcknowledged,
    ExecutionPartialFill,
    ExecutionFilled,
    ExecutionCancelled,
    ExecutionRejected,
    ExecutionCompleted,
)

logger = logging.getLogger(__name__)


class ExecutionOrchestrator:
    """Orchestrates trade execution pipelines, subscribing to calculated sizes and publishing status changes."""

    def __init__(self) -> None:
        self._state_store: IExecutionStateStore | None = None
        self._repository: IExecutionRepository | None = None
        self._execution_engine: IExecutionEngine | None = None
        self._event_bus: IEventBus | None = None
        self._config_provider: IConfigProvider | None = None
        self._container: IContainer | None = None

    def initialize(
        self,
        state_store: IExecutionStateStore,
        repository: IExecutionRepository,
        execution_engine: IExecutionEngine,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
    ) -> None:
        """Inject dependencies into the orchestrator."""
        self._state_store = state_store
        self._repository = repository
        self._execution_engine = execution_engine
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container

        if container is not None:
            if self._event_bus is None and container.has(IEventBus):
                self._event_bus = container.resolve(IEventBus)
            if self._config_provider is None and container.has(IConfigProvider):
                self._config_provider = container.resolve(IConfigProvider)

    def on_position_size_calculated(self, event: BaseEvent) -> Optional[ExecutionResult]:
        """Subscribe callback for 'system.position_size_calculated' events."""
        if not self._execution_engine or not self._repository or not self._state_store:
            raise OrchestratorError("ExecutionOrchestrator: Subsystem is not initialized.")

        try:
            payload = event.payload or {}
            state_dict = payload.get("state", {})
            result_dict = state_dict.get("result", {})
            size_dict = result_dict.get("position_size")

            if not result_dict.get("success") or not size_dict:
                logger.info("ExecutionOrchestrator: Skipping failed/unapproved position sizing result.")
                return None

            # Traceability IDs mapping
            execution_id = str(uuid.uuid4())
            request_id = payload.get("request_id") or str(uuid.uuid4())
            signal_id = payload.get("signal_id") or f"sig-{uuid.uuid4().hex[:8]}"
            strategy_id = payload.get("strategy_id") or f"strat-{uuid.uuid4().hex[:8]}"
            position_id = payload.get("position_id") or f"pos-{uuid.uuid4().hex[:8]}"
            correlation_id = payload.get("correlation_id") or f"corr-{uuid.uuid4().hex[:8]}"

            symbol = size_dict.get("symbol")
            timeframe = size_dict.get("timeframe")
            quantity = float(size_dict.get("quantity", 0.0))
            leverage = float(size_dict.get("leverage", 1.0))
            margin_required = float(size_dict.get("margin_required", 0.0))

            if quantity <= 0:
                logger.warning("ExecutionOrchestrator: Rejected position size calculated event with non-positive quantity: %s", quantity)
                return None

            # Resolve OrderSide explicitly from payload or TradingContext
            raw_side = payload.get("side") or size_dict.get("side")
            side: OrderSide | None = None
            if raw_side:
                side_str = str(getattr(raw_side, "value", raw_side)).upper()
                if "SELL" in side_str or "SHORT" in side_str or "BEARISH" in side_str:
                    side = OrderSide.SELL
                elif "BUY" in side_str or "LONG" in side_str or "BULLISH" in side_str:
                    side = OrderSide.BUY

            if side is None and self._container is not None:
                try:
                    from trading_context.core.interfaces import ITradingContextStateStore
                    if self._container.has(ITradingContextStateStore):
                        tc_store = self._container.resolve(ITradingContextStateStore)
                        snapshot = tc_store.get_snapshot(symbol)
                        if snapshot and timeframe in snapshot.states:
                            context = snapshot.states[timeframe]
                            if context and context.strategy_signal:
                                decision = context.strategy_signal.decision
                                decision_str = str(getattr(decision, "value", decision)).upper()
                                if "SELL" in decision_str:
                                    side = OrderSide.SELL
                                elif "BUY" in decision_str:
                                    side = OrderSide.BUY
                                else:
                                    # Fallback to direction
                                    dir_str = str(getattr(context.strategy_signal.direction, "value", context.strategy_signal.direction)).upper()
                                    if "BEARISH" in dir_str or "SHORT" in dir_str:
                                        side = OrderSide.SELL
                                    elif "BULLISH" in dir_str or "LONG" in dir_str:
                                        side = OrderSide.BUY
                except Exception as e:
                    logger.error("ExecutionOrchestrator: Failed to resolve TradingContext for side: %s", e)

            if side is None:
                logger.error(
                    "ExecutionOrchestrator: Cannot resolve order side for %s/%s. "
                    "Failing closed — no ExecutionRequest will be constructed and no event will be published.",
                    symbol,
                    timeframe,
                )
                return None


            # Compile request
            request = ExecutionRequest(
                execution_id=execution_id,
                request_id=request_id,
                signal_id=signal_id,
                strategy_id=strategy_id,
                position_id=position_id,
                correlation_id=correlation_id,
                symbol=symbol,
                timeframe=timeframe,
                quantity=quantity,
                price=None,  # Market order execution
                stop_price=None,
                side=side,
                order_type=OrderType.MARKET,
                time_in_force=OrderTimeInForce.GTC,
                leverage=leverage,
                margin_required=margin_required,
                timestamp=datetime.now(timezone.utc),
            )

            # Publish ExecutionRequested event
            self._publish_event(
                ExecutionRequested(payload=self._serialize_req(request))
            )
            return None

        except Exception as e:
            logger.error("ExecutionOrchestrator: Failed to process calculated size event: %s", e)
            return None

    def on_execution_approved(self, event: BaseEvent) -> Optional[ExecutionResult]:
        """Subscribe callback for 'system.execution_approved' events. Resolves broker routing and execution."""
        if not self._execution_engine or not self._repository or not self._state_store:
            raise OrchestratorError("ExecutionOrchestrator: Subsystem is not initialized.")

        try:
            payload = event.payload or {}
            # Reconstruct ExecutionRequest — catch deserialization failures explicitly (P1-B)
            try:
                request = ExecutionRequest(**payload)
            except PydanticValidationError as ve:
                execution_id = str(payload.get("execution_id") or f"unknown-{uuid.uuid4().hex[:8]}")
                correlation_id = str(payload.get("correlation_id") or f"unknown-{uuid.uuid4().hex[:8]}")
                logger.error(
                    "ExecutionOrchestrator: ExecutionRequest deserialization failed "
                    "(execution_id=%s). %d field error(s). Failing closed. Details: %s",
                    execution_id,
                    ve.error_count(),
                    ve.errors(),
                )
                if self._repository is not None:
                    audit_record = ExecutionAuditRecord(
                        execution_id=execution_id,
                        correlation_id=correlation_id,
                        actor="orchestrator",
                        action="REJECT",
                        before={"state": "PENDING"},
                        after={"state": "REJECTED", "reason": "ExecutionRequest deserialization failed"},
                        reason=f"PydanticValidationError: {ve.error_count()} field error(s). See logs for details.",
                    )
                    self._repository.save_audit_record(audit_record)
                return None
            symbol = request.symbol
            timeframe = request.timeframe

            # Process execution request via the Engine
            result = self._execution_engine.submit_execution(request)

            # Publish granular events based on order FSM result
            for order in result.orders:
                if order.state == OrderState.VALIDATED:
                    self._publish_event(ExecutionValidated(payload=self._serialize_order(order)))
                elif order.state == OrderState.REJECTED:
                    self._publish_event(ExecutionRejected(payload=self._serialize_order(order)))
                elif order.state == OrderState.SUBMITTED:
                    self._publish_event(ExecutionSubmitted(payload=self._serialize_order(order)))
                elif order.state == OrderState.ACKNOWLEDGED:
                    self._publish_event(ExecutionAcknowledged(payload=self._serialize_order(order)))
                elif order.state == OrderState.PARTIALLY_FILLED:
                    self._publish_event(ExecutionPartialFill(payload=self._serialize_order(order)))
                elif order.state == OrderState.FILLED:
                    self._publish_event(ExecutionValidated(payload=self._serialize_order(order)))
                    self._publish_event(ExecutionSubmitted(payload=self._serialize_order(order)))
                    self._publish_event(ExecutionFilled(payload=self._serialize_order(order)))

            # Publish ExecutionCompleted event with symbol and timeframe for generic handlers
            event_payload = result.model_dump()
            event_payload["symbol"] = symbol
            event_payload["timeframe"] = timeframe
            self._publish_event(
                ExecutionCompleted(payload=event_payload)
            )

            return result

        except Exception as e:
            logger.error("ExecutionOrchestrator: Failed to process execution approved event: %s", e)
            return None

    def _publish_event(self, event: BaseEvent) -> None:
        """Helper to publish events on the event bus."""
        if self._event_bus:
            self._event_bus.publish(event)

    def _serialize_req(self, req: ExecutionRequest) -> Dict[str, Any]:
        """Serialize ExecutionRequest."""
        return req.model_dump()

    def _serialize_order(self, order: Order) -> Dict[str, Any]:
        """Serialize Order."""
        return order.model_dump()
