from enum import Enum


class OrderType(str, Enum):
    """The type of execution order."""

    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP_LIMIT = "STOP_LIMIT"
    STOP_MARKET = "STOP_MARKET"
    OCO = "OCO"
    BRACKET = "BRACKET"
    TWAP = "TWAP"
    VWAP = "VWAP"
    ICEBERG = "ICEBERG"
    TRAILING_STOP = "TRAILING_STOP"


class OrderExecutionFlags(str, Enum):
    """Specific order execution constraints."""

    POST_ONLY = "POST_ONLY"
    REDUCE_ONLY = "REDUCE_ONLY"


class OrderSide(str, Enum):
    """The trade direction."""

    BUY = "BUY"
    SELL = "SELL"


class OrderState(str, Enum):
    """Execution state machine states for an order."""

    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class OrderTimeInForce(str, Enum):
    """Time-in-force parameters for order execution."""

    GTC = "GTC"  # Good 'Til Cancelled
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill


class ExecutionStatus(str, Enum):
    """Status indicating the resolution of an execution request."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


class ExecutionAlgorithmType(str, Enum):
    """Algorithmic execution strategy for the EMS layer."""

    DIRECT = "DIRECT"
    TWAP = "TWAP"
    VWAP = "VWAP"
    ICEBERG = "ICEBERG"
    POV = "POV"
    BRACKET = "BRACKET"
    OCO = "OCO"
    TRAILING_STOP = "TRAILING_STOP"


class IntentState(str, Enum):
    """Lifecycle states for an OrderIntent flowing through the OMS."""

    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    ROUTING = "ROUTING"
    ROUTED = "ROUTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RECOVERING = "RECOVERING"


class RoutingStrategy(str, Enum):
    """Venue routing strategy for execution requests."""

    SMART = "SMART"
    DIRECT = "DIRECT"
    CHEAPEST = "CHEAPEST"
    FASTEST = "FASTEST"


class OMSMode(str, Enum):
    """Operating mode of the OMS subsystem."""

    LIVE = "LIVE"
    PAPER = "PAPER"
    REPLAY = "REPLAY"
