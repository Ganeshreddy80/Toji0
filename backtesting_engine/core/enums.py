"""Enums for the Backtesting Engine (Sprint 7A)."""

from __future__ import annotations

import enum


class ReplayStatus(enum.Enum):
    """Lifecycle status of a historical data replay session."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SimulatedOrderStatus(enum.Enum):
    """Lifecycle status of a simulated broker order."""

    NEW = "NEW"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderType(enum.Enum):
    """Supported order execution types for backtest matching."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class TimeInForce(enum.Enum):
    """Time-in-force instructions for order matching."""

    GTC = "GTC"  # Good 'Till Cancelled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill


class PositionSide(enum.Enum):
    """Position side classification."""

    LONG = "LONG"
    SHORT = "SHORT"


class TradeStatus(enum.Enum):
    """Trade record lifecycle status."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class SlippageModel(enum.Enum):
    """Deterministic slippage simulation models."""

    NONE = "NONE"
    FIXED_TICKS = "FIXED_TICKS"
    FIXED_PERCENT = "FIXED_PERCENT"
    SPREAD_BASED = "SPREAD_BASED"
    VOLUME_BASED = "VOLUME_BASED"


class SpreadModel(enum.Enum):
    """Synthetic bid/ask spread models."""

    NONE = "NONE"
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"
    VOLATILITY_BASED = "VOLATILITY_BASED"


class CommissionModel(enum.Enum):
    """Execution fee structures."""

    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"
    MAKER_TAKER = "MAKER_TAKER"


class MarketImpactModel(enum.Enum):
    """Order size market impact models."""

    NONE = "NONE"
    LINEAR = "LINEAR"
    SQUARE_ROOT = "SQUARE_ROOT"

