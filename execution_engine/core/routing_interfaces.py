from typing import Any, List, Protocol
from execution_engine.core.models import ExecutionRequest, Order


class IExecutionPolicy(Protocol):
    """Interface defining specific speed vs transaction fee execution rules."""

    policy_name: str

    def evaluate_cost_benefit(self, request: ExecutionRequest, broker_options: List[str]) -> str:
        """Decide the optimal broker choice matching cost vs urgency targets."""
        ...


class IBrokerSelector(Protocol):
    """Interface evaluating broker liquidity pools and latency parameters."""

    def rank_brokers(self, request: ExecutionRequest, policy: IExecutionPolicy) -> List[str]:
        """Rank active registered broker adapters by execution compatibility."""
        ...


class IOrderSplitter(Protocol):
    """Interface for dividing large institutional trades into manageable baskets."""

    def split_request(self, request: ExecutionRequest, max_slice_qty: float) -> List[ExecutionRequest]:
        """Generate child requests from parent execution parameters."""
        ...


class ISmartOrderRouter(Protocol):
    """Interface for routing parent/child orders across multiple brokers."""

    def route_request(self, request: ExecutionRequest) -> List[Order]:
        """Distribute order legs to resolved targets."""
        ...


class IExecutionAlgorithm(Protocol):
    """Interface for execution algorithms like TWAP, VWAP, or Iceberg."""

    def execute_algo(self, request: ExecutionRequest, router: ISmartOrderRouter) -> None:
        """Run execution algorithm sequence."""
        ...
