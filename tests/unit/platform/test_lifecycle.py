"""Tests for the Lifecycle Manager."""

from __future__ import annotations

import pytest

from toji_platform.core.errors import ShutdownError, StartupError
from toji_platform.core.lifecycle import IHealthCheck, ILifecycle, LifecycleManager
from toji_platform.core.types import HealthStatus


class StubComponent(ILifecycle, IHealthCheck):
    """Minimal ILifecycle + IHealthCheck stub."""

    def __init__(self, component_name: str, fail_start: bool = False, fail_stop: bool = False):
        self._name = component_name
        self._fail_start = fail_start
        self._fail_stop = fail_stop
        self.started = False
        self.stopped = False

    @property
    def name(self) -> str:
        return self._name

    def start(self) -> None:
        if self._fail_start:
            raise RuntimeError(f"{self._name} start failure")
        self.started = True

    def stop(self) -> None:
        if self._fail_stop:
            raise RuntimeError(f"{self._name} stop failure")
        self.stopped = True

    def check_health(self) -> HealthStatus:
        return HealthStatus.HEALTHY if self.started else HealthStatus.UNHEALTHY


class TestLifecycleManager:
    """Tests for LifecycleManager."""

    def test_register_and_count(self):
        lm = LifecycleManager()
        lm.register(StubComponent("a"))
        lm.register(StubComponent("b"))
        assert lm.component_count == 2

    def test_start_all(self):
        lm = LifecycleManager()
        c1 = StubComponent("c1")
        c2 = StubComponent("c2")
        lm.register(c1)
        lm.register(c2)
        lm.start_all()
        assert c1.started is True
        assert c2.started is True
        assert lm.is_started is True

    def test_stop_all_reverses_order(self):
        lm = LifecycleManager()
        stop_order = []

        class OrderedComponent(StubComponent):
            def stop(self):
                stop_order.append(self._name)
                super().stop()

        lm.register(OrderedComponent("first"))
        lm.register(OrderedComponent("second"))
        lm.register(OrderedComponent("third"))
        lm.start_all()
        lm.stop_all()
        assert stop_order == ["third", "second", "first"]

    def test_start_failure_raises_startup_error(self):
        lm = LifecycleManager()
        lm.register(StubComponent("ok"))
        lm.register(StubComponent("bad", fail_start=True))
        with pytest.raises(StartupError, match="bad"):
            lm.start_all()

    def test_stop_failure_collects_errors(self):
        lm = LifecycleManager()
        lm.register(StubComponent("ok"))
        lm.register(StubComponent("bad", fail_stop=True))
        lm.start_all()
        with pytest.raises(ShutdownError, match="1 component"):
            lm.stop_all()

    def test_health_check(self):
        lm = LifecycleManager()
        lm.register(StubComponent("comp"))
        lm.start_all()
        results = lm.health_check()
        assert results["comp"] == HealthStatus.HEALTHY

    def test_health_check_before_start(self):
        lm = LifecycleManager()
        lm.register(StubComponent("comp"))
        results = lm.health_check()
        assert results["comp"] == HealthStatus.UNHEALTHY

    def test_is_started_flag(self):
        lm = LifecycleManager()
        assert lm.is_started is False
        lm.start_all()
        assert lm.is_started is True
        lm.stop_all()
        assert lm.is_started is False
