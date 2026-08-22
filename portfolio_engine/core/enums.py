from enum import Enum


class PositionSide(str, Enum):
    """Execution position direction classification."""

    LONG = "LONG"
    SHORT = "SHORT"


class PositionState(str, Enum):
    """Position lifecycle operational status."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
