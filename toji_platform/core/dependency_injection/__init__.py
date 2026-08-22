"""Dependency Injection Container.

Public API:
    - ``IContainer`` — abstract interface
    - ``Container`` — default implementation
"""

from toji_platform.core.dependency_injection.container import Container
from toji_platform.core.dependency_injection.interfaces import IContainer

__all__ = ["Container", "IContainer"]
