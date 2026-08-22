"""Typed domain registries for the Toji kernel.

Each registry is a thin subclass of ``BaseRegistry`` scoped to a
specific domain.  Custom validation logic is added via the
``_validate_item`` hook where appropriate.
"""

from __future__ import annotations

from typing import Any

from toji_platform.core.errors import RegistryValidationError
from toji_platform.core.registry.base import BaseRegistry


class ResearchModuleRegistry(BaseRegistry[Any]):
    """Registry for research analysis modules."""

    def __init__(self) -> None:
        super().__init__("ResearchModuleRegistry")


class AgentRegistry(BaseRegistry[Any]):
    """Registry for AI agents."""

    def __init__(self) -> None:
        super().__init__("AgentRegistry")


class PlaybookRegistry(BaseRegistry[Any]):
    """Registry for operational playbooks."""

    def __init__(self) -> None:
        super().__init__("PlaybookRegistry")


class PluginRegistry(BaseRegistry[Any]):
    """Registry for loaded plugins."""

    def __init__(self) -> None:
        super().__init__("PluginRegistry")


class StrategyRegistry(BaseRegistry[Any]):
    """Registry for trading / analysis strategies."""

    def __init__(self) -> None:
        super().__init__("StrategyRegistry")


class AssetRegistry(BaseRegistry[Any]):
    """Asset-agnostic registry for any tradable or researchable asset.

    Assets are identified by a free-form string key (e.g. ``"BTC"``,
    ``"AAPL"``, ``"EUR/USD"``).  The registry never hardcodes any
    specific asset or asset class.

    Validation ensures that registered items carry an ``asset_class``
    attribute matching one of the supported ``AssetClass`` enum values.
    """

    def __init__(self) -> None:
        super().__init__("AssetRegistry")

    def _validate_item(self, key: str, item: Any) -> None:
        """Ensure the item has a non-empty ``asset_class`` attribute."""
        asset_class = getattr(item, "asset_class", None)
        if asset_class is None:
            raise RegistryValidationError(
                key,
                "Asset must have an 'asset_class' attribute",
            )


class MemoryProviderRegistry(BaseRegistry[Any]):
    """Registry for memory / knowledge-store providers."""

    def __init__(self) -> None:
        super().__init__("MemoryProviderRegistry")


class AnalyticsProviderRegistry(BaseRegistry[Any]):
    """Registry for analytics / pipeline providers."""

    def __init__(self) -> None:
        super().__init__("AnalyticsProviderRegistry")
