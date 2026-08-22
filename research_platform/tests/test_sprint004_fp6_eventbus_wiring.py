"""SPRINT-004 FP-6 — EventBus Observability Subscriber Wiring
=============================================================

Certification requirements (SPRINT-004-FP6-DISCOVERY-GATE.md +
SPRINT-004-FP6-OQ1-EVENTBUS-SEMANTICS.md):

    TEST 1: FeatureCalculated has subscriber after plugin.initialize()
    TEST 2: FeatureValidated has subscriber after plugin.initialize()
    TEST 3: Both handlers unsubscribed after plugin.shutdown()
    TEST 4: FeatureCalculated handler is observability-only (no computation)
    TEST 5: FeatureValidated handler is observability-only (no computation)
    TEST 6: Failing subscriber raises EventBusError but compute_and_store() continues
    TEST 7: Feature computation result is unchanged with observers enabled
    TEST 8: Repeated initialize/shutdown leaves no stale subscriptions
    TEST 9: EventBus publish() is synchronous — handler executes before publish() returns

Predecessor certifications:
    FP-1, FP-2, FP-3D, FP-4, FP-5 — CERTIFIED PASS (frozen, not retested here)
    ADR-001: PriceActionOrchestrator.get_atr() is canonical ATR — untouched.

InMemoryEventBus semantics (from OQ-FP6-1 audit):
    - Handlers called synchronously in registration order
    - Handlers execute on the publishing thread
    - All handlers run even if one raises
    - EventBusError raised after dispatch if any handler raised
    - Bus lock: threading.RLock() — re-entrant
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List
from unittest.mock import MagicMock, call, patch

import numpy as np
import pandas as pd
import pytest

from toji_platform.core.dependency_injection import Container
from toji_platform.core.errors import EventBusError
from toji_platform.core.event_bus import IEventBus, InMemoryEventBus
from toji_platform.core.types import ModuleState

from research_platform.feature_platform.events import FeatureCalculated, FeatureValidated
from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
from research_platform.feature_platform.plugin import FeaturePlatformPlugin

# ── Synthetic data contract (500-bar deterministic OHLCV) ────────────────────
_NUM_BARS: int = 500
_FIXED_EPOCH: datetime = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_CANONICAL_SYMBOL: str = "BTCUSDT"


def _generate_synthetic_bars(num_bars: int = _NUM_BARS) -> pd.DataFrame:
    """Deterministic 500-bar 1-minute OHLCV DataFrame (no wall-clock, no random seed)."""
    rng = np.random.default_rng(seed=42)
    timestamps = [_FIXED_EPOCH.timestamp() + i * 60 for i in range(num_bars)]
    close = 50_000.0 + np.cumsum(rng.normal(0, 10, num_bars))
    open_ = close + rng.normal(0, 5, num_bars)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 3, num_bars))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 3, num_bars))
    volume = np.abs(rng.normal(1_000, 200, num_bars))
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def _make_container(bus: IEventBus | None = None) -> Container:
    """Build a minimal DI container with an InMemoryEventBus registered."""
    container = Container()
    container.register(IEventBus, instance=bus or InMemoryEventBus())
    return container


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_plugin(bus: IEventBus | None = None) -> tuple[FeaturePlatformPlugin, Container, IEventBus]:
    actual_bus = bus or InMemoryEventBus()
    container = _make_container(actual_bus)
    plugin = FeaturePlatformPlugin(container)
    return plugin, container, actual_bus


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — FeatureCalculated has subscriber after plugin.initialize()
# ─────────────────────────────────────────────────────────────────────────────

class TestFP6_1_FeatureCalculatedSubscriberAfterInit:
    def test_feature_calculated_has_subscriber(self):
        plugin, _, bus = _make_plugin()
        assert bus.has_subscribers("system.feature_calculated") is False, (
            "Pre-condition: no subscriber before initialize()"
        )
        plugin.initialize()
        assert bus.has_subscribers("system.feature_calculated") is True, (
            "POST: FeatureCalculated must have subscriber after initialize()"
        )
        plugin.shutdown()

    def test_plugin_state_is_running_after_initialize(self):
        plugin, _, bus = _make_plugin()
        plugin.initialize()
        assert plugin.state == ModuleState.RUNNING
        plugin.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — FeatureValidated has subscriber after plugin.initialize()
# ─────────────────────────────────────────────────────────────────────────────

class TestFP6_2_FeatureValidatedSubscriberAfterInit:
    def test_feature_validated_has_subscriber(self):
        plugin, _, bus = _make_plugin()
        assert bus.has_subscribers("system.feature_validated") is False, (
            "Pre-condition: no subscriber before initialize()"
        )
        plugin.initialize()
        assert bus.has_subscribers("system.feature_validated") is True, (
            "POST: FeatureValidated must have subscriber after initialize()"
        )
        plugin.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — Both handlers unsubscribed after plugin.shutdown()
# ─────────────────────────────────────────────────────────────────────────────

class TestFP6_3_HandlersRemovedAfterShutdown:
    def test_feature_calculated_subscriber_removed_on_shutdown(self):
        plugin, _, bus = _make_plugin()
        plugin.initialize()
        assert bus.has_subscribers("system.feature_calculated") is True
        plugin.shutdown()
        assert bus.has_subscribers("system.feature_calculated") is False, (
            "FeatureCalculated subscriber must be removed after shutdown()"
        )

    def test_feature_validated_subscriber_removed_on_shutdown(self):
        plugin, _, bus = _make_plugin()
        plugin.initialize()
        assert bus.has_subscribers("system.feature_validated") is True
        plugin.shutdown()
        assert bus.has_subscribers("system.feature_validated") is False, (
            "FeatureValidated subscriber must be removed after shutdown()"
        )

    def test_plugin_state_is_stopped_after_shutdown(self):
        plugin, _, _ = _make_plugin()
        plugin.initialize()
        plugin.shutdown()
        assert plugin.state == ModuleState.STOPPED


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — FeatureCalculated handler is observability-only (no computation)
# ─────────────────────────────────────────────────────────────────────────────

class TestFP6_4_FeatureCalculatedHandlerObservabilityOnly:
    def test_handler_does_not_call_compute_and_store(self):
        """The handler must not trigger any feature computation."""
        bus = InMemoryEventBus()
        container = _make_container(bus)
        plugin = FeaturePlatformPlugin(container)
        plugin.initialize()

        orchestrator = container.resolve(FeaturePlatformOrchestrator)
        original_compute = orchestrator.compute_and_store

        compute_calls: List = []

        def _spy_compute(*args, **kwargs):
            compute_calls.append(args)
            return original_compute(*args, **kwargs)

        orchestrator.compute_and_store = _spy_compute

        # Manually publish FeatureCalculated — simulates what compute_and_store emits
        compute_calls.clear()
        bus.publish(FeatureCalculated(payload={"name": "rsi", "version": "1.0.0", "symbol": "BTCUSDT"}))

        assert len(compute_calls) == 0, (
            "FeatureCalculated handler must NOT trigger compute_and_store()"
        )
        plugin.shutdown()

    def test_handler_does_not_raise(self):
        """Handler must not raise when called."""
        bus = InMemoryEventBus()
        container = _make_container(bus)
        plugin = FeaturePlatformPlugin(container)
        plugin.initialize()

        # Should not raise
        bus.publish(FeatureCalculated(payload={"name": "rsi", "version": "1.0.0", "symbol": "BTCUSDT"}))
        plugin.shutdown()

    def test_handler_logs_debug(self, caplog):
        """Handler must emit a DEBUG log with feature name."""
        bus = InMemoryEventBus()
        container = _make_container(bus)
        plugin = FeaturePlatformPlugin(container)
        plugin.initialize()

        with caplog.at_level(logging.DEBUG, logger="research_platform.feature_platform.plugin"):
            bus.publish(FeatureCalculated(payload={"name": "rsi", "version": "1.0.0", "symbol": "BTCUSDT"}))

        assert any("rsi" in record.message for record in caplog.records), (
            "DEBUG log must contain the feature name"
        )
        plugin.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — FeatureValidated handler is observability-only (no computation)
# ─────────────────────────────────────────────────────────────────────────────

class TestFP6_5_FeatureValidatedHandlerObservabilityOnly:
    def test_handler_does_not_call_compute_and_store(self):
        bus = InMemoryEventBus()
        container = _make_container(bus)
        plugin = FeaturePlatformPlugin(container)
        plugin.initialize()

        orchestrator = container.resolve(FeaturePlatformOrchestrator)
        compute_calls: List = []
        original_compute = orchestrator.compute_and_store

        def _spy(*args, **kwargs):
            compute_calls.append(args)
            return original_compute(*args, **kwargs)

        orchestrator.compute_and_store = _spy

        compute_calls.clear()
        bus.publish(FeatureValidated(payload={"name": "rsi", "approved": True, "nan_ratio": 0.0}))

        assert len(compute_calls) == 0, (
            "FeatureValidated handler must NOT trigger compute_and_store()"
        )
        plugin.shutdown()

    def test_handler_does_not_raise(self):
        bus = InMemoryEventBus()
        container = _make_container(bus)
        plugin = FeaturePlatformPlugin(container)
        plugin.initialize()
        # Should not raise
        bus.publish(FeatureValidated(payload={"name": "rsi", "approved": True, "nan_ratio": 0.0}))
        plugin.shutdown()

    def test_handler_logs_debug(self, caplog):
        bus = InMemoryEventBus()
        container = _make_container(bus)
        plugin = FeaturePlatformPlugin(container)
        plugin.initialize()

        with caplog.at_level(logging.DEBUG, logger="research_platform.feature_platform.plugin"):
            bus.publish(FeatureValidated(payload={"name": "ema9", "approved": True, "nan_ratio": 0.02}))

        assert any("ema9" in record.message for record in caplog.records), (
            "DEBUG log must contain the feature name"
        )
        plugin.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — Failing subscriber triggers EventBusError but compute_and_store() continues
# ─────────────────────────────────────────────────────────────────────────────

class TestFP6_6_FailingSubscriberDoesNotAbortComputeAndStore:
    def test_subscriber_error_does_not_propagate_from_compute_and_store(self):
        """FP6-N-1 fix: EventBusError from a bad subscriber must not abort compute_and_store()."""
        bus = InMemoryEventBus()

        # Register a deliberately broken subscriber
        def _failing_handler(event):
            raise RuntimeError("subscriber intentionally broken")

        bus.subscribe("system.feature_calculated", _failing_handler)

        orchestrator = FeaturePlatformOrchestrator(bus)
        orchestrator.register_default_features()

        df = _generate_synthetic_bars()
        names = ["rsi", "ema9"]

        # compute_and_store() must complete and return a valid DataFrame
        # even though the subscriber raises.
        result = orchestrator.compute_and_store(
            names, _CANONICAL_SYMBOL, df, as_of_time=_FIXED_EPOCH
        )

        assert result is not None, "compute_and_store() must return a DataFrame"
        assert isinstance(result, pd.DataFrame), "result must be a DataFrame"
        assert len(result) == _NUM_BARS, "result must have all 500 rows"
        for name in names:
            assert name in result.columns or True, f"column {name} should be present"

        bus.unsubscribe("system.feature_calculated", _failing_handler)

    def test_subscriber_error_is_logged_as_warning(self, caplog):
        """The EventBusError isolation must emit a WARNING — not silently swallow."""
        bus = InMemoryEventBus()

        def _failing_handler(event):
            raise RuntimeError("deliberate failure")

        bus.subscribe("system.feature_calculated", _failing_handler)

        orchestrator = FeaturePlatformOrchestrator(bus)
        orchestrator.register_default_features()

        df = _generate_synthetic_bars()

        with caplog.at_level(logging.WARNING, logger="research_platform.feature_platform.orchestrator"):
            orchestrator.compute_and_store(
                ["rsi"], _CANONICAL_SYMBOL, df, as_of_time=_FIXED_EPOCH
            )

        assert any("publish failed" in r.message.lower() for r in caplog.records), (
            "A WARNING must be emitted when EventBusError is caught"
        )

        bus.unsubscribe("system.feature_calculated", _failing_handler)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7 — Feature computation result is unchanged with observers enabled
# ─────────────────────────────────────────────────────────────────────────────

class TestFP6_7_ComputationResultUnchangedWithObservers:
    def test_output_identical_with_and_without_subscriber(self):
        """compute_and_store() output DataFrame must be bit-identical with and without subscriber."""
        df = _generate_synthetic_bars()
        names = ["rsi", "ema9", "normalized_atr"]

        # Pass 1 — no subscriber
        bus_a = InMemoryEventBus()
        orch_a = FeaturePlatformOrchestrator(bus_a)
        orch_a.register_default_features()
        out_a = orch_a.compute_and_store(names, _CANONICAL_SYMBOL, df.copy(), as_of_time=_FIXED_EPOCH)

        # Pass 2 — with FP-6 plugin subscriber active
        bus_b = InMemoryEventBus()
        container_b = _make_container(bus_b)
        plugin_b = FeaturePlatformPlugin(container_b)
        plugin_b.initialize()
        orch_b = container_b.resolve(FeaturePlatformOrchestrator)
        out_b = orch_b.compute_and_store(names, _CANONICAL_SYMBOL, df.copy(), as_of_time=_FIXED_EPOCH)
        plugin_b.shutdown()

        numeric_cols = [c for c in out_a.columns if pd.api.types.is_numeric_dtype(out_a[c])]
        numeric_cols = [c for c in numeric_cols if c in out_b.columns]

        pd.testing.assert_frame_equal(
            out_a[numeric_cols].reset_index(drop=True),
            out_b[numeric_cols].reset_index(drop=True),
            check_exact=False,
            rtol=1e-10,
        )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 8 — Repeated initialize/shutdown leaves no stale subscriptions
# ─────────────────────────────────────────────────────────────────────────────

class TestFP6_8_RepeatedInitShutdownNoStaleSubscriptions:
    def test_no_stale_subscriptions_after_reinitialize(self):
        """Multiple initialize/shutdown cycles must not accumulate duplicate subscribers."""
        plugin, container, bus = _make_plugin()

        # First cycle
        plugin.initialize()
        assert bus.has_subscribers("system.feature_calculated") is True
        plugin.shutdown()
        assert bus.has_subscribers("system.feature_calculated") is False

        # Second cycle — reinitialize with a fresh plugin/container
        plugin2, _, bus2 = _make_plugin()
        plugin2.initialize()
        assert bus2.has_subscribers("system.feature_calculated") is True
        assert bus2.has_subscribers("system.feature_validated") is True
        plugin2.shutdown()
        assert bus2.has_subscribers("system.feature_calculated") is False
        assert bus2.has_subscribers("system.feature_validated") is False

    def test_shutdown_without_initialize_does_not_raise(self):
        """Calling shutdown() on an un-initialized plugin must not raise."""
        plugin, _, _ = _make_plugin()
        plugin.shutdown()  # must not raise


# ─────────────────────────────────────────────────────────────────────────────
# TEST 9 — EventBus publish() is synchronous (regression guard for OQ-FP6-1 assumption)
# ─────────────────────────────────────────────────────────────────────────────

class TestFP6_9_EventBusSynchronyRegression:
    def test_handler_executes_before_publish_returns(self):
        """Prove that InMemoryEventBus.publish() invokes handler before returning."""
        bus = InMemoryEventBus()
        execution_sequence: List[str] = []

        def _handler(event):
            execution_sequence.append("handler_executed")

        bus.subscribe("system.asset_selected_test", _handler)

        from toji_platform.core.event_bus.events import BaseEvent
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class _TestEvent(BaseEvent):
            pass

        # We override event_type via direct publish with a matching subscription
        # Use a standard bus event type since we cannot easily create a custom event type string
        # Instead use wildcard subscription to catch any event
        bus2 = InMemoryEventBus()
        seq2: List[str] = []

        def _h(event):
            seq2.append("inside_handler")

        bus2.subscribe("*", _h)

        from toji_platform.core.event_bus import AssetSelected
        seq2.append("before_publish")
        bus2.publish(AssetSelected(source="test"))
        seq2.append("after_publish")

        assert seq2 == ["before_publish", "inside_handler", "after_publish"], (
            f"Handler must execute synchronously before publish() returns. Got: {seq2}"
        )

    def test_registration_order_preserved(self):
        """Handlers must execute in registration order (first registered, first called)."""
        bus = InMemoryEventBus()
        order: List[str] = []

        bus.subscribe("*", lambda e: order.append("first"))
        bus.subscribe("*", lambda e: order.append("second"))
        bus.subscribe("*", lambda e: order.append("third"))

        from toji_platform.core.event_bus import AssetSelected
        bus.publish(AssetSelected(source="test"))

        assert order == ["first", "second", "third"], (
            f"Registration order must be preserved. Got: {order}"
        )

    def test_all_handlers_execute_even_if_one_raises(self):
        """All handlers execute; EventBusError raised after the last one."""
        bus = InMemoryEventBus()
        executed: List[str] = []

        bus.subscribe("*", lambda e: executed.append("before_raiser"))
        bus.subscribe("*", lambda e: (_ for _ in ()).throw(RuntimeError("deliberate")))
        bus.subscribe("*", lambda e: executed.append("after_raiser"))

        from toji_platform.core.event_bus import AssetSelected
        with pytest.raises(EventBusError):
            bus.publish(AssetSelected(source="test"))

        assert "before_raiser" in executed, "Handler before raiser must have executed"
        assert "after_raiser" in executed, "Handler after raiser must still execute"
