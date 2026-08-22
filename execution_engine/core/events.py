from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class ExecutionRequested(BaseEvent):
    """Fired when an execution request is submitted to the queue."""
    pass


@dataclass(frozen=True)
class ExecutionValidated(BaseEvent):
    """Fired when an execution request successfully passes pre-trade validation checks."""
    pass


@dataclass(frozen=True)
class ExecutionSubmitted(BaseEvent):
    """Fired when an order is successfully sent to the broker adapter."""
    pass


@dataclass(frozen=True)
class ExecutionAcknowledged(BaseEvent):
    """Fired when the broker adapter confirms receipt of an order."""
    pass


@dataclass(frozen=True)
class ExecutionPartialFill(BaseEvent):
    """Fired when a partial fill is reported by the broker adapter."""
    pass


@dataclass(frozen=True)
class ExecutionFilled(BaseEvent):
    """Fired when an order is completely filled."""
    pass


@dataclass(frozen=True)
class ExecutionCancelled(BaseEvent):
    """Fired when an order is successfully cancelled."""
    pass


@dataclass(frozen=True)
class ExecutionRejected(BaseEvent):
    """Fired when an order is rejected by the broker adapter or validator."""
    pass


@dataclass(frozen=True)
class ExecutionCompleted(BaseEvent):
    """Fired when an execution request completes (either fully filled or terminated)."""
    pass


@dataclass(frozen=True)
class ExecutionApproved(BaseEvent):
    """Fired when an execution request is approved by the risk engine and ready for submission."""
    pass


# ── Sprint 8: Institutional OMS & EMS Events ──────────────────────────────


@dataclass(frozen=True)
class OrderIntentCreated(BaseEvent):
    """Fired when a new OrderIntent is created from a sizing result."""
    pass


@dataclass(frozen=True)
class OrderIntentValidated(BaseEvent):
    """Fired when an OrderIntent passes OMS pre-trade validation."""
    pass


@dataclass(frozen=True)
class OrderIntentApproved(BaseEvent):
    """Fired when an OrderIntent is approved and ready for routing."""
    pass


@dataclass(frozen=True)
class OrderIntentRejected(BaseEvent):
    """Fired when an OrderIntent is rejected by validation or risk checks."""
    pass


@dataclass(frozen=True)
class OrderRouted(BaseEvent):
    """Fired when the EMS routes an order to a specific broker venue."""
    pass


@dataclass(frozen=True)
class BrokerSelected(BaseEvent):
    """Fired when the routing engine selects a broker adapter."""
    pass


@dataclass(frozen=True)
class OrderSliceSubmitted(BaseEvent):
    """Fired when an algorithmic execution slice is submitted as a child order."""
    pass


@dataclass(frozen=True)
class ExecutionAlgorithmStarted(BaseEvent):
    """Fired when an EMS execution algorithm begins processing slices."""
    pass


@dataclass(frozen=True)
class ExecutionAlgorithmProgress(BaseEvent):
    """Fired when an EMS execution algorithm reports slice progress."""
    pass


@dataclass(frozen=True)
class ExecutionAlgorithmCompleted(BaseEvent):
    """Fired when an EMS execution algorithm finishes all slices."""
    pass


@dataclass(frozen=True)
class OMSStateChanged(BaseEvent):
    """Fired when the OMS operational state counters update."""
    pass


@dataclass(frozen=True)
class OMSRecovered(BaseEvent):
    """Fired when the OMS successfully completes crash recovery reconciliation."""
    pass

