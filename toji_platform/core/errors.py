"""Kernel-level exception hierarchy.

Every exception raised by the Toji kernel inherits from
``TojiKernelError`` so callers can catch platform errors
without catching unrelated exceptions.
"""

from __future__ import annotations


class TojiKernelError(Exception):
    """Root exception for all Toji kernel errors."""


# ── Configuration ──────────────────────────────────────────────────────────
class ConfigurationError(TojiKernelError):
    """Raised when configuration loading or validation fails."""


class MissingConfigError(ConfigurationError):
    """Raised when a required configuration key is absent."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Required configuration key missing: '{key}'")


# ── Registry ───────────────────────────────────────────────────────────────
class RegistryError(TojiKernelError):
    """Base error for registry operations."""


class DuplicateRegistrationError(RegistryError):
    """Raised when a key is already registered."""

    def __init__(self, key: str, registry_name: str) -> None:
        self.key = key
        self.registry_name = registry_name
        super().__init__(
            f"Key '{key}' is already registered in {registry_name}"
        )


class NotRegisteredError(RegistryError):
    """Raised when accessing a key that is not registered."""

    def __init__(self, key: str, registry_name: str) -> None:
        self.key = key
        self.registry_name = registry_name
        super().__init__(
            f"Key '{key}' is not registered in {registry_name}"
        )


class RegistryValidationError(RegistryError):
    """Raised when a registry entry fails validation."""

    def __init__(self, key: str, reason: str) -> None:
        self.key = key
        self.reason = reason
        super().__init__(f"Validation failed for '{key}': {reason}")


# ── Plugin ─────────────────────────────────────────────────────────────────
class PluginError(TojiKernelError):
    """Base error for plugin operations."""


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load or initialize."""

    def __init__(self, plugin_name: str, reason: str) -> None:
        self.plugin_name = plugin_name
        self.reason = reason
        super().__init__(f"Plugin '{plugin_name}' failed to load: {reason}")


class PluginNotFoundError(PluginError):
    """Raised when a requested plugin is not found."""

    def __init__(self, plugin_name: str) -> None:
        self.plugin_name = plugin_name
        super().__init__(f"Plugin '{plugin_name}' not found")


class PluginDependencyError(PluginError):
    """Raised when plugin dependencies cannot be resolved."""

    def __init__(self, plugin_name: str, missing: list[str]) -> None:
        self.plugin_name = plugin_name
        self.missing = missing
        deps = ", ".join(missing)
        super().__init__(
            f"Plugin '{plugin_name}' has unresolved dependencies: {deps}"
        )


# ── Lifecycle ──────────────────────────────────────────────────────────────
class LifecycleError(TojiKernelError):
    """Raised when a lifecycle transition fails."""


class StartupError(LifecycleError):
    """Raised when a module fails during startup."""


class ShutdownError(LifecycleError):
    """Raised when a module fails during shutdown."""


# ── Dependency Injection ───────────────────────────────────────────────────
class ContainerError(TojiKernelError):
    """Base error for DI container operations."""


class ServiceNotFoundError(ContainerError):
    """Raised when resolving a service that is not registered."""

    def __init__(self, service_type: type | str) -> None:
        name = service_type if isinstance(service_type, str) else service_type.__name__
        super().__init__(f"Service not found in container: '{name}'")


class DuplicateServiceError(ContainerError):
    """Raised when registering a service key that already exists."""

    def __init__(self, service_type: type | str) -> None:
        name = service_type if isinstance(service_type, str) else service_type.__name__
        super().__init__(f"Service already registered in container: '{name}'")


# ── Event Bus ──────────────────────────────────────────────────────────────
class EventBusError(TojiKernelError):
    """Raised when event publishing or subscription fails."""
