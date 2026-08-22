"""Configuration Manager — environment-driven, profile-aware config.

Public API:
    - ``IConfigProvider`` — abstract interface
    - ``ConfigurationManager`` — default implementation
"""

from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.configuration.manager import ConfigurationManager

__all__ = ["ConfigurationManager", "IConfigProvider"]
