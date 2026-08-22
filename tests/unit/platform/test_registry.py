"""Tests for the Registry System."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from toji_platform.core.errors import (
    DuplicateRegistrationError,
    NotRegisteredError,
    RegistryValidationError,
)
from toji_platform.core.registry import (
    AgentRegistry,
    AnalyticsProviderRegistry,
    AssetRegistry,
    BaseRegistry,
    MemoryProviderRegistry,
    PlaybookRegistry,
    PluginRegistry,
    ResearchModuleRegistry,
    StrategyRegistry,
)
from toji_platform.core.types import AssetClass


class TestBaseRegistry:
    """Tests for the generic BaseRegistry."""

    def test_register_and_get(self):
        reg = BaseRegistry[str]("TestRegistry")
        reg.register("key1", "value1")
        assert reg.get("key1") == "value1"

    def test_duplicate_registration_raises(self):
        reg = BaseRegistry[str]("TestRegistry")
        reg.register("key1", "value1")
        with pytest.raises(DuplicateRegistrationError, match="key1"):
            reg.register("key1", "value2")

    def test_get_nonexistent_raises(self):
        reg = BaseRegistry[str]("TestRegistry")
        with pytest.raises(NotRegisteredError, match="missing"):
            reg.get("missing")

    def test_unregister(self):
        reg = BaseRegistry[str]("TestRegistry")
        reg.register("key1", "value1")
        removed = reg.unregister("key1")
        assert removed == "value1"
        assert reg.has("key1") is False

    def test_unregister_nonexistent_raises(self):
        reg = BaseRegistry[str]("TestRegistry")
        with pytest.raises(NotRegisteredError, match="missing"):
            reg.unregister("missing")

    def test_has(self):
        reg = BaseRegistry[str]("TestRegistry")
        assert reg.has("key1") is False
        reg.register("key1", "value1")
        assert reg.has("key1") is True

    def test_count(self):
        reg = BaseRegistry[str]("TestRegistry")
        assert reg.count() == 0
        reg.register("a", "1")
        reg.register("b", "2")
        assert reg.count() == 2

    def test_list_all(self):
        reg = BaseRegistry[str]("TestRegistry")
        reg.register("a", "1")
        reg.register("b", "2")
        result = reg.list_all()
        assert result == {"a": "1", "b": "2"}
        # Ensure it returns a copy
        result["c"] = "3"
        assert reg.count() == 2

    def test_discover_no_criteria_returns_all(self):
        reg = BaseRegistry[str]("TestRegistry")
        reg.register("a", "1")
        reg.register("b", "2")
        assert len(reg.discover()) == 2

    def test_discover_with_attribute_filter(self):
        @dataclass
        class Item:
            category: str
            value: int

        reg = BaseRegistry[Item]("TestRegistry")
        reg.register("a", Item(category="x", value=1))
        reg.register("b", Item(category="y", value=2))
        reg.register("c", Item(category="x", value=3))
        results = reg.discover(category="x")
        assert len(results) == 2

    def test_validate_passes_by_default(self):
        reg = BaseRegistry[str]("TestRegistry")
        assert reg.validate("key", "value") is True

    def test_name_property(self):
        reg = BaseRegistry[str]("MyRegistry")
        assert reg.name == "MyRegistry"


class TestAssetRegistry:
    """Tests for the AssetRegistry with custom validation."""

    def test_rejects_item_without_asset_class(self):
        reg = AssetRegistry()
        with pytest.raises(RegistryValidationError, match="asset_class"):
            reg.register("BTC", {"name": "Bitcoin"})

    def test_accepts_item_with_asset_class(self):
        @dataclass
        class Asset:
            asset_class: AssetClass
            name: str

        reg = AssetRegistry()
        reg.register("BTC", Asset(asset_class=AssetClass.CRYPTO, name="Bitcoin"))
        assert reg.has("BTC")

    def test_is_asset_agnostic(self):
        """The registry accepts any asset, not just crypto."""

        @dataclass
        class Asset:
            asset_class: AssetClass
            name: str

        reg = AssetRegistry()
        reg.register("AAPL", Asset(asset_class=AssetClass.STOCKS, name="Apple"))
        reg.register("EUR/USD", Asset(asset_class=AssetClass.FOREX, name="Euro/Dollar"))
        reg.register("GOLD", Asset(asset_class=AssetClass.COMMODITIES, name="Gold"))
        assert reg.count() == 3


class TestAllRegistries:
    """Ensure all typed registries instantiate correctly."""

    @pytest.mark.parametrize(
        "registry_cls, expected_name",
        [
            (ResearchModuleRegistry, "ResearchModuleRegistry"),
            (AgentRegistry, "AgentRegistry"),
            (PlaybookRegistry, "PlaybookRegistry"),
            (PluginRegistry, "PluginRegistry"),
            (StrategyRegistry, "StrategyRegistry"),
            (AssetRegistry, "AssetRegistry"),
            (MemoryProviderRegistry, "MemoryProviderRegistry"),
            (AnalyticsProviderRegistry, "AnalyticsProviderRegistry"),
        ],
    )
    def test_registry_name(self, registry_cls, expected_name):
        reg = registry_cls()
        assert reg.name == expected_name
        assert reg.count() == 0
