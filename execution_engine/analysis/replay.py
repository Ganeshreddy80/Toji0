from datetime import datetime, timezone
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from execution_engine.core.models import ExecutionRequest
from execution_engine.core.enums import OrderState
from execution_engine.analysis.execution_engine import ExecutionEngine


class ReplayJournal(BaseModel):
    """Immutable sequence of historical execution requests and states for deterministic replay validation."""

    requests: List[ExecutionRequest] = Field(default_factory=list)
    expected_order_states: Dict[str, OrderState] = Field(default_factory=dict)


class ReplayResult(BaseModel):
    """Calculated comparison summary of replay vs original execution records."""

    mismatches: List[str] = Field(default_factory=list)
    success: bool = True
    replayed_orders_count: int = 0
    duration_ms: float = 0.0


class ExecutionReplayEngine:
    """Deterministically replays historical journal sequences to check execution logic consistency."""

    def __init__(self, engine: ExecutionEngine) -> None:
        self._engine = engine

    def run_replay(self, journal: ReplayJournal) -> ReplayResult:
        """Run replay loops by resetting duplicate trackers and verifying final order states."""
        start_time = datetime.now(timezone.utc)
        mismatches = []
        orders_replayed = 0

        for req in journal.requests:
            try:
                # Bypass duplicate checker for replay execution
                self._engine._validator._deduplicator.clear()
                self._engine._state_store.clear()

                result = self._engine.submit_execution(req)
                orders_replayed += len(result.orders)

                for order in result.orders:
                    expected_state = journal.expected_order_states.get(order.client_order_id)
                    if expected_state is not None and order.state != expected_state:
                        mismatches.append(
                            f"State divergence for order {order.client_order_id}: "
                            f"expected {expected_state.value}, got {order.state.value}."
                        )
            except Exception as e:
                mismatches.append(f"Replay execution failed for request {req.request_id}: {e}")

        end_time = datetime.now(timezone.utc)
        duration_ms = (end_time - start_time).total_seconds() * 1000.0

        return ReplayResult(
            mismatches=mismatches,
            success=len(mismatches) == 0,
            replayed_orders_count=orders_replayed,
            duration_ms=duration_ms,
        )
