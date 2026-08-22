"""Sprint 8 — Institutional OMS & EMS Test Suite.

Tests:
- IntentStateMachine FSM transitions (valid + invalid)
- New Pydantic model construction (OrderIntent, RoutingDecision, etc.)
- OMS Core lifecycle (submit, complete, cancel, reject)
- EMS Engine algorithm selection and execution (Direct, TWAP, VWAP, Iceberg, POV, Bracket, OCO)
- Recovery Manager reconciliation
- Order Book Tracker utilities
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from execution_engine.core.enums import (
    ExecutionAlgorithmType,
    ExecutionStatus,
    IntentState,
    OMSMode,
    OrderSide,
    OrderState,
    OrderTimeInForce,
    OrderType,
    RoutingStrategy,
)
from execution_engine.core.exceptions import InvalidStateTransitionError
from execution_engine.core.models import (
    BrokerStatus,
    ExecutionAlgorithmState,
    ExecutionSlice,
    OMSConfig,
    OMSState,
    OrderBookLevel,
    OrderBookSnapshot,
    OrderIntent,
    RoutingDecision,
)
from execution_engine.core.state_machine import IntentStateMachine


# ── Helpers ───────────────────────────────────────────────────────────

def _make_intent(**overrides) -> OrderIntent:
    """Factory for a valid test OrderIntent."""
    defaults = {
        "intent_id": "test-intent-001",
        "execution_id": "exec-001",
        "request_id": "req-001",
        "signal_id": "sig-001",
        "strategy_id": "strat-001",
        "position_id": "pos-001",
        "correlation_id": "corr-001",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "quantity": 1.0,
    }
    defaults.update(overrides)
    return OrderIntent(**defaults)


# ── IntentStateMachine Tests ──────────────────────────────────────────


class TestIntentStateMachine:
    """Tests for the IntentStateMachine FSM transitions."""

    def test_valid_full_lifecycle(self):
        """Happy path: CREATED → VALIDATING → VALIDATED → APPROVED → ROUTING → ROUTED → EXECUTING → COMPLETED."""
        transitions = [
            (IntentState.CREATED, IntentState.VALIDATING),
            (IntentState.VALIDATING, IntentState.VALIDATED),
            (IntentState.VALIDATED, IntentState.APPROVED),
            (IntentState.APPROVED, IntentState.ROUTING),
            (IntentState.ROUTING, IntentState.ROUTED),
            (IntentState.ROUTED, IntentState.EXECUTING),
            (IntentState.EXECUTING, IntentState.COMPLETED),
        ]
        for from_state, to_state in transitions:
            IntentStateMachine.validate_transition(from_state, to_state)

    def test_rejection_from_created(self):
        IntentStateMachine.validate_transition(IntentState.CREATED, IntentState.REJECTED)

    def test_rejection_from_validating(self):
        IntentStateMachine.validate_transition(IntentState.VALIDATING, IntentState.REJECTED)

    def test_cancellation_from_approved(self):
        IntentStateMachine.validate_transition(IntentState.APPROVED, IntentState.CANCELLED)

    def test_failure_from_executing(self):
        IntentStateMachine.validate_transition(IntentState.EXECUTING, IntentState.FAILED)

    def test_recovery_from_failed(self):
        IntentStateMachine.validate_transition(IntentState.FAILED, IntentState.RECOVERING)

    def test_completion_from_recovering(self):
        IntentStateMachine.validate_transition(IntentState.RECOVERING, IntentState.COMPLETED)

    def test_invalid_transition_completed_to_created(self):
        with pytest.raises(InvalidStateTransitionError):
            IntentStateMachine.validate_transition(IntentState.COMPLETED, IntentState.CREATED)

    def test_invalid_transition_rejected_to_approved(self):
        with pytest.raises(InvalidStateTransitionError):
            IntentStateMachine.validate_transition(IntentState.REJECTED, IntentState.APPROVED)

    def test_invalid_transition_cancelled_to_executing(self):
        with pytest.raises(InvalidStateTransitionError):
            IntentStateMachine.validate_transition(IntentState.CANCELLED, IntentState.EXECUTING)

    def test_self_transition_allowed(self):
        IntentStateMachine.validate_transition(IntentState.EXECUTING, IntentState.EXECUTING)

    def test_terminal_states(self):
        terminals = IntentStateMachine.get_terminal_states()
        assert IntentState.COMPLETED in terminals
        assert IntentState.REJECTED in terminals
        assert IntentState.CANCELLED in terminals
        assert IntentState.EXECUTING not in terminals

    def test_is_active(self):
        assert IntentStateMachine.is_active(IntentState.EXECUTING) is True
        assert IntentStateMachine.is_active(IntentState.COMPLETED) is False
        assert IntentStateMachine.is_active(IntentState.REJECTED) is False


# ── Model Construction Tests ──────────────────────────────────────────


class TestOmsModels:
    """Tests for Sprint 8 Pydantic model construction."""

    def test_order_intent_construction(self):
        intent = _make_intent()
        assert intent.intent_id == "test-intent-001"
        assert intent.state == IntentState.CREATED
        assert intent.algorithm == ExecutionAlgorithmType.DIRECT
        assert intent.quantity == 1.0

    def test_order_intent_immutability(self):
        intent = _make_intent()
        with pytest.raises(Exception):
            intent.state = IntentState.APPROVED

    def test_order_intent_model_copy(self):
        intent = _make_intent()
        updated = intent.model_copy(update={"state": IntentState.VALIDATED})
        assert updated.state == IntentState.VALIDATED
        assert intent.state == IntentState.CREATED

    def test_routing_decision_construction(self):
        rd = RoutingDecision(
            decision_id="rd-001",
            intent_id="test-intent-001",
            execution_id="exec-001",
            correlation_id="corr-001",
            broker_id="paper",
            strategy=RoutingStrategy.DIRECT,
            reason="Test routing.",
        )
        assert rd.broker_id == "paper"
        assert rd.strategy == RoutingStrategy.DIRECT

    def test_execution_algorithm_state_construction(self):
        algo_state = ExecutionAlgorithmState(
            algo_id="algo-001",
            intent_id="test-intent-001",
            execution_id="exec-001",
            correlation_id="corr-001",
            algorithm=ExecutionAlgorithmType.TWAP,
            total_quantity=10.0,
            filled_quantity=5.0,
            remaining_quantity=5.0,
            total_slices=5,
            completed_slices=3,
            progress_pct=50.0,
        )
        assert algo_state.algorithm == ExecutionAlgorithmType.TWAP
        assert algo_state.progress_pct == 50.0

    def test_execution_slice_construction(self):
        s = ExecutionSlice(
            slice_id="slice-001",
            algo_id="algo-001",
            intent_id="test-intent-001",
            execution_id="exec-001",
            slice_index=0,
            quantity=2.0,
        )
        assert s.slice_index == 0
        assert s.is_submitted is False
        assert s.is_filled is False

    def test_oms_config_defaults(self):
        config = OMSConfig()
        assert config.mode == OMSMode.PAPER
        assert config.default_broker_id == "paper"
        assert config.max_open_orders == 100

    def test_oms_state_construction(self):
        state = OMSState(
            total_intents=10,
            active_intents=3,
            completed_intents=5,
            rejected_intents=2,
        )
        assert state.total_intents == 10
        assert state.active_intents == 3

    def test_order_book_snapshot_construction(self):
        snap = OrderBookSnapshot(
            symbol="BTCUSDT",
            bids=[OrderBookLevel(price=50000.0, quantity=1.0)],
            asks=[OrderBookLevel(price=50010.0, quantity=1.0)],
            mid_price=50005.0,
            spread=10.0,
        )
        assert snap.mid_price == 50005.0
        assert len(snap.bids) == 1

    def test_broker_status_construction(self):
        status = BrokerStatus(
            broker_id="paper",
            is_connected=True,
            latency_ms=1.5,
        )
        assert status.is_connected is True


# ── OMS Core Tests ────────────────────────────────────────────────────


class TestOmsCore:
    """Tests for the OMS Core lifecycle manager."""

    def _make_oms(self):
        from execution_engine.brokers.broker_router import BrokerRouter
        from execution_engine.core.validator import ExecutionValidator, ExecutionDeduplicator
        from execution_engine.core.models import ExecutionConfig
        from execution_engine.oms.oms_core import OmsCore

        config = OMSConfig(default_broker_id="paper")
        broker_router = BrokerRouter()

        # Register a mock broker adapter
        from unittest.mock import MagicMock
        mock_adapter = MagicMock()
        mock_adapter.ping.return_value = True
        broker_router.register_adapter("paper", mock_adapter)

        exec_config = ExecutionConfig(max_slippage_pct=0.05, max_position_size=10.0)
        deduplicator = ExecutionDeduplicator()
        validator = ExecutionValidator(config=exec_config, deduplicator=deduplicator)

        return OmsCore(
            config=config,
            broker_router=broker_router,
            validator=validator,
        )

    def test_submit_intent_happy_path(self):
        oms = self._make_oms()
        intent = _make_intent()
        result = oms.submit_intent(intent)
        assert result.state == IntentState.ROUTED

    def test_submit_intent_invalid_quantity(self):
        oms = self._make_oms()
        intent = _make_intent(quantity=0.0)
        result = oms.submit_intent(intent)
        assert result.state == IntentState.REJECTED
        assert "Quantity must be positive" in result.rejection_reasons[0]

    def test_submit_intent_limit_without_price(self):
        oms = self._make_oms()
        intent = _make_intent(order_type=OrderType.LIMIT, price=None)
        result = oms.submit_intent(intent)
        assert result.state == IntentState.REJECTED
        assert any("price" in r.lower() for r in result.rejection_reasons)

    def test_complete_intent(self):
        oms = self._make_oms()
        intent = _make_intent()
        routed = oms.submit_intent(intent)
        completed = oms.complete_intent(routed.intent_id)
        assert completed.state == IntentState.COMPLETED

    def test_cancel_intent(self):
        oms = self._make_oms()
        intent = _make_intent()
        routed = oms.submit_intent(intent)
        cancelled = oms.cancel_intent(routed.intent_id)
        assert cancelled.state == IntentState.CANCELLED

    def test_oms_state_counters(self):
        oms = self._make_oms()
        intent = _make_intent()
        oms.submit_intent(intent)
        state = oms.get_oms_state()
        assert state.total_intents == 1

    def test_get_active_intents(self):
        oms = self._make_oms()
        intent = _make_intent()
        oms.submit_intent(intent)
        active = oms.get_active_intents()
        assert len(active) == 1

    def test_bracket_validation_missing_prices(self):
        oms = self._make_oms()
        intent = _make_intent(
            algorithm=ExecutionAlgorithmType.BRACKET,
            bracket_stop_loss=None,
            bracket_take_profit=None,
        )
        result = oms.submit_intent(intent)
        assert result.state == IntentState.REJECTED

    def test_iceberg_validation_missing_display_qty(self):
        oms = self._make_oms()
        intent = _make_intent(
            algorithm=ExecutionAlgorithmType.ICEBERG,
            iceberg_display_quantity=None,
        )
        result = oms.submit_intent(intent)
        assert result.state == IntentState.REJECTED


# ── EMS Engine Tests ──────────────────────────────────────────────────


class TestEmsEngine:
    """Tests for the EMS Engine algorithm execution."""

    def _make_ems_with_paper_broker(self):
        from execution_engine.brokers.broker_router import BrokerRouter
        from execution_engine.brokers.paper_broker import PaperBroker
        from execution_engine.ems.ems_engine import EmsEngine

        broker = PaperBroker(config_settings={"initial_balance": 100000.0, "latency_ms": 0.0})
        broker.connect()
        router = BrokerRouter()
        router.register_adapter("paper", broker)

        return EmsEngine(broker_router=router), broker

    def test_direct_execution(self):
        ems, broker = self._make_ems_with_paper_broker()
        intent = _make_intent(algorithm=ExecutionAlgorithmType.DIRECT, price=50000.0)
        result = ems.execute_intent(intent, "paper")
        assert result.status == ExecutionStatus.EXECUTED
        assert len(result.orders) >= 1

    def test_twap_execution(self):
        ems, broker = self._make_ems_with_paper_broker()
        intent = _make_intent(
            algorithm=ExecutionAlgorithmType.TWAP,
            price=50000.0,
            algo_params={"num_slices": 3, "interval_seconds": 0.01},
        )
        result = ems.execute_intent(intent, "paper")
        assert result.status == ExecutionStatus.EXECUTED
        assert len(result.orders) == 3

    def test_vwap_execution(self):
        ems, broker = self._make_ems_with_paper_broker()
        intent = _make_intent(
            algorithm=ExecutionAlgorithmType.VWAP,
            price=50000.0,
            algo_params={"num_slices": 5, "interval_seconds": 0.01},
        )
        result = ems.execute_intent(intent, "paper")
        assert result.status == ExecutionStatus.EXECUTED
        assert len(result.orders) == 5

    def test_iceberg_execution(self):
        ems, broker = self._make_ems_with_paper_broker()
        intent = _make_intent(
            algorithm=ExecutionAlgorithmType.ICEBERG,
            quantity=10.0,
            price=50000.0,
            iceberg_display_quantity=2.0,
        )
        result = ems.execute_intent(intent, "paper")
        assert result.status == ExecutionStatus.EXECUTED
        assert len(result.orders) == 5  # 10.0 / 2.0 = 5 slices

    def test_pov_execution(self):
        ems, broker = self._make_ems_with_paper_broker()
        intent = _make_intent(
            algorithm=ExecutionAlgorithmType.POV,
            price=50000.0,
            algo_params={
                "participation_rate": 0.1,
                "num_slices": 4,
                "interval_seconds": 0.01,
                "estimated_market_volume": 100.0,
            },
        )
        result = ems.execute_intent(intent, "paper")
        assert result.status == ExecutionStatus.EXECUTED

    def test_bracket_execution(self):
        ems, broker = self._make_ems_with_paper_broker()
        intent = _make_intent(
            algorithm=ExecutionAlgorithmType.BRACKET,
            price=50000.0,
            bracket_take_profit=52000.0,
            bracket_stop_loss=48000.0,
        )
        result = ems.execute_intent(intent, "paper")
        assert result.status == ExecutionStatus.EXECUTED
        assert len(result.orders) >= 3  # entry + TP + SL

    def test_oco_execution(self):
        ems, broker = self._make_ems_with_paper_broker()
        intent = _make_intent(
            algorithm=ExecutionAlgorithmType.OCO,
            price=50000.0,
            oco_stop_price=48000.0,
        )
        result = ems.execute_intent(intent, "paper")
        assert result.status in (ExecutionStatus.EXECUTED, ExecutionStatus.FAILED)

    def test_algo_state_tracking(self):
        ems, broker = self._make_ems_with_paper_broker()
        intent = _make_intent(algorithm=ExecutionAlgorithmType.DIRECT, price=50000.0)
        ems.execute_intent(intent, "paper")
        state = ems.get_algo_state(intent.intent_id)
        assert state is not None
        assert state.is_complete is True

    def test_cancel_execution(self):
        ems, broker = self._make_ems_with_paper_broker()
        # Execute then cancel
        intent = _make_intent(algorithm=ExecutionAlgorithmType.DIRECT, price=50000.0)
        ems.execute_intent(intent, "paper")
        ems.cancel_execution(intent.intent_id)
        state = ems.get_algo_state(intent.intent_id)
        # Already completed, so cancel won't flip it
        assert state.is_complete is True


# ── Order Book Tracker Tests ──────────────────────────────────────────


class TestOrderBookTracker:
    """Tests for the order book tracker utility."""

    def test_generate_simulated_book(self):
        from execution_engine.oms.order_book import OrderBookTracker

        tracker = OrderBookTracker()
        book = tracker.generate_simulated_book(
            symbol="BTCUSDT",
            mid_price=50000.0,
            spread_pct=0.001,
            levels=5,
        )
        assert book.symbol == "BTCUSDT"
        assert len(book.bids) == 5
        assert len(book.asks) == 5
        assert book.mid_price == 50000.0

    def test_get_mid_price(self):
        from execution_engine.oms.order_book import OrderBookTracker

        tracker = OrderBookTracker()
        tracker.generate_simulated_book("ETHUSDT", 3000.0)
        mid = tracker.get_mid_price("ETHUSDT")
        assert mid == 3000.0

    def test_get_spread(self):
        from execution_engine.oms.order_book import OrderBookTracker

        tracker = OrderBookTracker()
        tracker.generate_simulated_book("ETHUSDT", 3000.0, spread_pct=0.002)
        spread = tracker.get_spread("ETHUSDT")
        assert spread is not None
        assert spread > 0

    def test_get_available_liquidity(self):
        from execution_engine.oms.order_book import OrderBookTracker

        tracker = OrderBookTracker()
        tracker.generate_simulated_book("BTCUSDT", 50000.0, levels=5, base_quantity=100.0)
        liquidity = tracker.get_available_liquidity("BTCUSDT", "bid", depth=3)
        assert liquidity > 0

    def test_estimate_market_impact(self):
        from execution_engine.oms.order_book import OrderBookTracker

        tracker = OrderBookTracker()
        tracker.generate_simulated_book("BTCUSDT", 50000.0, levels=10, base_quantity=100.0)
        impact = tracker.estimate_market_impact("BTCUSDT", "buy", 50.0)
        assert impact >= 0

    def test_nonexistent_symbol(self):
        from execution_engine.oms.order_book import OrderBookTracker

        tracker = OrderBookTracker()
        assert tracker.get_book("NONEXISTENT") is None
        assert tracker.get_mid_price("NONEXISTENT") is None

    def test_clear(self):
        from execution_engine.oms.order_book import OrderBookTracker

        tracker = OrderBookTracker()
        tracker.generate_simulated_book("BTCUSDT", 50000.0)
        tracker.clear()
        assert tracker.get_book("BTCUSDT") is None


# ── Recovery Manager Tests ────────────────────────────────────────────


class TestRecoveryManager:
    """Tests for the OMS crash recovery manager."""

    def test_reconcile_pre_broker_intents(self):
        from unittest.mock import MagicMock
        from execution_engine.brokers.broker_router import BrokerRouter
        from execution_engine.oms.recovery import RecoveryManager
        from execution_engine.oms.oms_core import IntentStore

        router = BrokerRouter()
        mock = MagicMock()
        router.register_adapter("paper", mock)

        recovery = RecoveryManager(broker_router=router)
        store = IntentStore()

        # Pre-broker intents should be cancelled
        intents = [
            _make_intent(intent_id="pre-1", state=IntentState.CREATED),
            _make_intent(intent_id="pre-2", state=IntentState.VALIDATING),
            _make_intent(intent_id="pre-3", state=IntentState.VALIDATED),
        ]
        for i in intents:
            store.add_intent(i)

        results = recovery.reconcile(intents, store)
        assert results["pre-1"] == "CANCELLED"
        assert results["pre-2"] == "CANCELLED"
        assert results["pre-3"] == "CANCELLED"

    def test_reconcile_terminal_intents_skipped(self):
        from unittest.mock import MagicMock
        from execution_engine.brokers.broker_router import BrokerRouter
        from execution_engine.oms.recovery import RecoveryManager
        from execution_engine.oms.oms_core import IntentStore

        router = BrokerRouter()
        mock = MagicMock()
        router.register_adapter("paper", mock)

        recovery = RecoveryManager(broker_router=router)
        store = IntentStore()

        intent = _make_intent(intent_id="completed-1", state=IntentState.COMPLETED)
        store.add_intent(intent)

        results = recovery.reconcile([intent], store)
        assert results["completed-1"] == "COMPLETED"


# ── Enum Tests ────────────────────────────────────────────────────────


class TestNewEnums:
    """Tests for Sprint 8 enum additions."""

    def test_execution_algorithm_type_values(self):
        assert ExecutionAlgorithmType.DIRECT.value == "DIRECT"
        assert ExecutionAlgorithmType.TWAP.value == "TWAP"
        assert ExecutionAlgorithmType.VWAP.value == "VWAP"
        assert ExecutionAlgorithmType.ICEBERG.value == "ICEBERG"
        assert ExecutionAlgorithmType.POV.value == "POV"
        assert ExecutionAlgorithmType.BRACKET.value == "BRACKET"
        assert ExecutionAlgorithmType.OCO.value == "OCO"
        assert ExecutionAlgorithmType.TRAILING_STOP.value == "TRAILING_STOP"

    def test_intent_state_values(self):
        assert IntentState.CREATED.value == "CREATED"
        assert IntentState.RECOVERING.value == "RECOVERING"

    def test_routing_strategy_values(self):
        assert RoutingStrategy.SMART.value == "SMART"
        assert RoutingStrategy.DIRECT.value == "DIRECT"
        assert RoutingStrategy.CHEAPEST.value == "CHEAPEST"
        assert RoutingStrategy.FASTEST.value == "FASTEST"

    def test_oms_mode_values(self):
        assert OMSMode.LIVE.value == "LIVE"
        assert OMSMode.PAPER.value == "PAPER"
        assert OMSMode.REPLAY.value == "REPLAY"
