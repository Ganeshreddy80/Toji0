"""Plugin Manager — framework for extensible capabilities.

Public API:
    - ``IPlugin`` — interface every plugin must implement
    - ``IPluginManager`` — manager interface
    - ``PluginManager`` — default implementation
"""

from toji_platform.core.plugin_manager.interfaces import IPlugin, IPluginManager
from toji_platform.core.plugin_manager.manager import PluginManager

__all__ = ["IPlugin", "IPluginManager", "PluginManager"]
