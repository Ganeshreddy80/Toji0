"""Regression tests for Sprint 1 Task 4A: P1 fail-closed fixes.

Covers:
- P1-A: Unresolved order side must fail closed (no ExecutionRequest built, no event emitted).
- P1-B: Malformed ExecutionRequest payload must fail closed with audit record written.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from execution_engine.core.events import ExecutionRequested
from position_sizing.core.events import PositionSizeCalculated

from execution_engine.core.orchestrator import ExecutionOrchestrator
from execution_engine.core.repository import ExecutionRepository
from execution_engine.core.state import ExecutionStateStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_orchestrator(repository=None) -> ExecutionOrchestrator:
    mock_engine = MagicMock()
    mock_state_store = ExecutionStateStore()
    repo = repository or ExecutionRepository()

    orch = ExecutionOrchestrator()
    orch.initialize(
        state_store=mock_state_store,
        repository=repo,
        execution_engine=mock_engine,
        event_bus=None,
        config_provider=None,
        container=None,
    )
    return orch


def _size_event(side=None) -> PositionSizeCalculated:
    """Build a PositionSizeCalculated event. Omit side to simulate unresolvable direction."""
    payload: dict = {
        "request_id": "req-p1a",
        "signal_id": "sig-p1a",
        "strategy_id": "strat-p1a",
        "position_id": "pos-p1a",
        "correlation_id": "corr-p1a",
        "state": {
            "result": {
                "success": True,
                "position_size": {
                    "symbol": "BTCUSDT",
                    "timeframe": "1h",
                    "quantity": 1.0,
                    "leverage": 1.0,
                    "margin_required": 0.0,
                },
            }
        },
    }
    if side is not None:
        payload["side"] = side
    return PositionSizeCalculated(payload=payload)


def _approved_event(payload: dict):
    """Build an ExecutionApproved event with the given payload."""
    from execution_engine.core.events import ExecutionApproved
    return ExecutionApproved(source="test", payload=payload)


# ---------------------------------------------------------------------------
# P1-A: Unresolved side must fail closed
# ---------------------------------------------------------------------------

class TestP1A_UnresolvedSideFailClosed:

    def test_no_side_returns_none(self):
        """P1-A: on_position_size_calculated returns None when side cannot be resolved."""
        orch = _make_orchestrator()
        event = _size_event(side=None)
        result = orch.on_position_size_calculated(event)
        assert result is None

    def test_no_side_does_not_publish_execution_requested(self):
        """P1-A: No ExecutionRequested event is published when side is unresolvable."""
        mock_event_bus = MagicMock()
        orch = _make_orchestrator()
        orch._event_bus = mock_event_bus

        event = _size_event(side=None)
        orch.on_position_size_calculated(event)

        mock_event_bus.publish.assert_not_called()

    def test_no_side_logs_error(self, caplog):
        """P1-A: An ERROR-level log is emitted when side is unresolvable."""
        import logging
        orch = _make_orchestrator()
        event = _size_event(side=None)

        with caplog.at_level(logging.ERROR, logger="execution_engine.core.orchestrator"):
            orch.on_position_size_calculated(event)

        error_msgs = [r.message for r in caplog.records if r.levelno == logging.ERROR]
        assert any("Cannot resolve order side" in m for m in error_msgs)

    def test_resolved_buy_side_publishes_event(self):
        """P1-A: A clearly resolved BUY side does not fail closed."""
        orch = _make_orchestrator()
        mock_bus = MagicMock()
        orch._event_bus = mock_bus

        event = _size_event(side="BUY")
        orch.on_position_size_calculated(event)

        mock_bus.publish.assert_called_once()

    def test_resolved_sell_side_publishes_event(self):
        """P1-A: A clearly resolved SELL side does not fail closed."""
        orch = _make_orchestrator()
        mock_bus = MagicMock()
        orch._event_bus = mock_bus

        event = _size_event(side="SELL")
        orch.on_position_size_calculated(event)

        mock_bus.publish.assert_called_once()


# ---------------------------------------------------------------------------
# P1-B: Malformed ExecutionRequest payload must fail closed with audit record
# ---------------------------------------------------------------------------

class TestP1B_MalformedPayloadFailClosed:

    def test_empty_payload_returns_none(self):
        """P1-B: on_execution_approved returns None when payload is empty."""
        orch = _make_orchestrator()
        event = _approved_event({})
        result = orch.on_execution_approved(event)
        assert result is None

    def test_empty_payload_writes_audit_record(self):
        """P1-B: An audit record is written to the repository when deserialization fails."""
        repo = ExecutionRepository()
        orch = _make_orchestrator(repository=repo)

        event = _approved_event({"execution_id": "exec-bad", "correlation_id": "corr-bad"})
        orch.on_execution_approved(event)

        reject_records = [r for r in repo._audit_records if r.action == "REJECT" and r.actor == "orchestrator"]
        assert len(reject_records) >= 1

    def test_audit_record_uses_execution_id_from_payload(self):
        """P1-B: Audit record captures execution_id and correlation_id from malformed payload."""
        repo = ExecutionRepository()
        orch = _make_orchestrator(repository=repo)

        event = _approved_event({
            "execution_id": "exec-malformed-123",
            "correlation_id": "corr-malformed-456",
        })
        orch.on_execution_approved(event)

        reject_records = [r for r in repo._audit_records if r.action == "REJECT" and r.actor == "orchestrator"]
        assert len(reject_records) == 1
        assert reject_records[0].execution_id == "exec-malformed-123"
        assert reject_records[0].correlation_id == "corr-malformed-456"

    def test_empty_payload_logs_error(self, caplog):
        """P1-B: An ERROR-level log is emitted on deserialization failure."""
        import logging
        orch = _make_orchestrator()
        event = _approved_event({})

        with caplog.at_level(logging.ERROR, logger="execution_engine.core.orchestrator"):
            orch.on_execution_approved(event)

        error_msgs = [r.message for r in caplog.records if r.levelno == logging.ERROR]
        assert any("deserialization failed" in m for m in error_msgs)

    def test_valid_payload_is_not_rejected(self):
        """P1-B: A valid serialised ExecutionRequest is not rejected by the guard."""
        from execution_engine.core.enums import ExecutionStatus, OrderSide, OrderType, OrderTimeInForce
        from execution_engine.core.models import ExecutionRequest, ExecutionResult

        valid_req = ExecutionRequest(
            execution_id="exec-ok",
            request_id="req-ok",
            signal_id="sig-ok",
            strategy_id="strat-ok",
            position_id="pos-ok",
            correlation_id="corr-ok",
            symbol="BTCUSDT",
            timeframe="1h",
            quantity=1.0,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            time_in_force=OrderTimeInForce.GTC,
            timestamp=datetime.now(timezone.utc),
        )

        orch = _make_orchestrator()
        mock_result = ExecutionResult(
            execution_id="exec-ok",
            request_id="req-ok",
            correlation_id="corr-ok",
            status=ExecutionStatus.EXECUTED,
            orders=[],
        )
        orch._execution_engine.submit_execution.return_value = mock_result

        event = _approved_event(valid_req.model_dump(mode="json"))
        result = orch.on_execution_approved(event)

        assert result is not None
        assert result.status == ExecutionStatus.EXECUTED
