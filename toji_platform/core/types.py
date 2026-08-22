"""Shared type definitions and enums for the Toji kernel.

All kernel modules reference these canonical types rather than
defining their own primitives, ensuring consistency across the
entire platform.
"""

from __future__ import annotations

import enum
from typing import Any, NewType

# ── Identity Types ─────────────────────────────────────────────────────────
ModuleId = NewType("ModuleId", str)
EventId = NewType("EventId", str)
PluginId = NewType("PluginId", str)
RegistryKey = NewType("RegistryKey", str)
CorrelationId = NewType("CorrelationId", str)


# ── Module State ───────────────────────────────────────────────────────────
class ModuleState(enum.Enum):
    """Lifecycle state of a kernel module or plugin."""

    CREATED = "created"
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


# ── Configuration Profiles ─────────────────────────────────────────────────
class Profile(enum.Enum):
    """Runtime environment profile."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


# ── Asset Classes ──────────────────────────────────────────────────────────
class AssetClass(enum.Enum):
    """Supported asset class categories.

    The platform is asset-agnostic — this enum defines *categories*,
    not individual assets.  The AssetRegistry stores concrete assets
    keyed by arbitrary string identifiers.
    """

    CRYPTO = "crypto"
    STOCKS = "stocks"
    FOREX = "forex"
    COMMODITIES = "commodities"
    INDICES = "indices"
    ETF = "etf"


# ── Health Status ──────────────────────────────────────────────────────────
class HealthStatus(enum.Enum):
    """Result of a health-check probe."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# ── Generic Payload ────────────────────────────────────────────────────────
Payload = dict[str, Any]
"""Arbitrary key-value payload attached to events and messages."""
