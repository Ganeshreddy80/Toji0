"""Tests for the Dependency Injection Container."""

from __future__ import annotations

import pytest

from toji_platform.core.dependency_injection import Container
from toji_platform.core.errors import DuplicateServiceError, ServiceNotFoundError


class TestContainer:
    """Tests for the DI Container."""

    def test_register_instance_and_resolve(self):
        c = Container()
        c.register("config", instance={"key": "value"})
        assert c.resolve("config") == {"key": "value"}

    def test_register_with_type_key(self):
        c = Container()

        class MyService:
            pass

        svc = MyService()
        c.register(MyService, instance=svc)
        assert c.resolve(MyService) is svc

    def test_has(self):
        c = Container()
        assert c.has("config") is False
        c.register("config", instance="val")
        assert c.has("config") is True

    def test_resolve_nonexistent_raises(self):
        c = Container()
        with pytest.raises(ServiceNotFoundError, match="missing"):
            c.resolve("missing")

    def test_duplicate_registration_raises(self):
        c = Container()
        c.register("svc", instance="a")
        with pytest.raises(DuplicateServiceError, match="svc"):
            c.register("svc", instance="b")

    def test_factory_singleton(self):
        c = Container()
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return {"created": call_count}

        c.register("svc", factory=factory, singleton=True)
        result1 = c.resolve("svc")
        result2 = c.resolve("svc")
        assert result1 is result2  # same instance
        assert call_count == 1

    def test_factory_transient(self):
        c = Container()
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return {"created": call_count}

        c.register("svc", factory=factory, singleton=False)
        result1 = c.resolve("svc")
        result2 = c.resolve("svc")
        assert result1 is not result2  # different instances
        assert call_count == 2

    def test_reset_clears_all(self):
        c = Container()
        c.register("a", instance="1")
        c.register("b", instance="2")
        c.reset()
        assert c.has("a") is False
        assert c.has("b") is False

    def test_must_provide_instance_or_factory(self):
        c = Container()
        with pytest.raises(ValueError, match="instance.*factory"):
            c.register("bad")

    def test_register_with_type_key_and_factory(self):
        c = Container()

        class SvcA:
            pass

        c.register(SvcA, factory=SvcA)
        result = c.resolve(SvcA)
        assert isinstance(result, SvcA)
