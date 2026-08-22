"""Registry System — typed service registries for the Toji kernel.

Public API:
    - ``IRegistry`` — generic abstract interface
    - ``BaseRegistry`` — reusable generic implementation
    - Typed registries: ``ResearchModuleRegistry``, ``AgentRegistry``,
      ``PlaybookRegistry``, ``PluginRegistry``, ``StrategyRegistry``,
      ``AssetRegistry``, ``MemoryProviderRegistry``,
      ``AnalyticsProviderRegistry``
"""

from toji_platform.core.registry.base import BaseRegistry
from toji_platform.core.registry.interfaces import IRegistry
from toji_platform.core.registry.registries import (
    AgentRegistry,
    AnalyticsProviderRegistry,
    AssetRegistry,
    MemoryProviderRegistry,
    PlaybookRegistry,
    PluginRegistry,
    ResearchModuleRegistry,
    StrategyRegistry,
)

__all__ = [
    "AgentRegistry",
    "AnalyticsProviderRegistry",
    "AssetRegistry",
    "BaseRegistry",
    "IRegistry",
    "MemoryProviderRegistry",
    "PlaybookRegistry",
    "PluginRegistry",
    "ResearchModuleRegistry",
    "StrategyRegistry",
]
