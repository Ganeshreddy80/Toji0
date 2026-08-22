from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from execution_engine.core.enums import (
    ExecutionAlgorithmType,
    ExecutionStatus,
    IntentState,
    OMSMode,
    OrderSide,
    OrderState,
    OrderTimeInForce,
    OrderType,
    RoutingStrategy,
)


class BrokerConfig(BaseModel):
    """Sub-config for broker selections and connections."""
    broker_selection: str = Field(default="paper", description="The active broker identifier.")
    commission_model: Dict[str, Any] = Field(default_factory=dict, description="Broker fee rates.")
    heartbeat_interval_seconds: int = Field(default=30, description="Ping frequency.")
    reconnect_interval_seconds: int = Field(default=5, description="Sleep time between connection retries.")
    model_config = ConfigDict(frozen=True)


class QueueConfig(BaseModel):
    """Sub-config for execution queues."""
    max_queue_size: int = Field(default=1000, description="Max items in the queue.")
    prioritization_enabled: bool = Field(default=True, description="Enable priority sorting.")
    model_config = ConfigDict(frozen=True)


class RetryConfig(BaseModel):
    """Sub-config for error retry handling."""
    max_retries: int = Field(default=3, description="Max retries.")
    backoff_multiplier: float = Field(default=2.0, description="Backoff multiplier.")
    initial_delay_seconds: float = Field(default=0.5, description="Initial delay in seconds.")
    model_config = ConfigDict(frozen=True)


class PaperBrokerConfig(BaseModel):
    """Sub-config for simulated paper broker settings."""
    initial_balance: float = Field(default=10000.0, description="Starting cash.")
    latency_ms: float = Field(default=10.0, description="Latency simulator.")
    slippage_rate: float = Field(default=0.0005, description="Slippage simulation rate.")
    commission_rate: float = Field(default=0.001, description="Commission simulation rate.")
    rejection_rate: float = Field(default=0.0, description="Mock rejection rate.")
    timeout_rate: float = Field(default=0.0, description="Mock API timeout rate.")
    timeout_ms: float = Field(default=1000.0, description="Mock API timeout duration.")
    max_order_age_seconds: float = Field(default=10.0, description="Maximum age before stale.")
    model_config = ConfigDict(frozen=True)


class ExecutionConfig(BaseModel):
    """Configuration model for execution parameters to prevent hardcoding."""

    timeouts_ms: Dict[str, int] = Field(default_factory=dict, description="Timeouts mapped by operation.")
    retry_policy: Dict[str, Any] = Field(default_factory=dict, description="Retry retry count and sleep configuration.")
    broker_selection: str = Field(default="paper", description="The active broker identifier.")
    commission_model: Dict[str, Any] = Field(default_factory=dict, description="Broker fee rates.")
    slippage_model: Dict[str, Any] = Field(default_factory=dict, description="Mock slippage parameters.")
    paper_broker_settings: Dict[str, Any] = Field(default_factory=dict, description="Paper trading parameters.")
    heartbeat_interval_seconds: int = Field(default=30, description="Ping frequency.")
    reconnect_interval_seconds: int = Field(default=5, description="Sleep time between connection retries.")
    precision_rules: Dict[str, Dict[str, int]] = Field(default_factory=dict, description="Decimal precisions by symbol.")
    tick_size_rules: Dict[str, float] = Field(default_factory=dict, description="Price tick steps by symbol.")
    min_notional_rules: Dict[str, float] = Field(default_factory=dict, description="Min execution size by symbol.")

    # New sub-configs
    broker: BrokerConfig = Field(default_factory=BrokerConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    paper_broker: PaperBrokerConfig = Field(default_factory=PaperBrokerConfig)

    model_config = ConfigDict(frozen=True)


class ExecutionRequest(BaseModel):
    """Unified trade execution request carrying full traceability details."""

    execution_id: str = Field(..., description="Unique UUID for this execution flow.")
    request_id: str = Field(..., description="Originating PositionSizingResult UUID.")
    signal_id: str = Field(..., description="Upstream signal identifier.")
    strategy_id: str = Field(..., description="Upstream strategy identifier.")
    position_id: str = Field(..., description="Identifier mapping the target position.")
    correlation_id: str = Field(..., description="Correlation ID for end-to-end audit tracing.")
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    quantity: float = Field(..., description="Target quantity to execute.")
    price: Optional[float] = Field(default=None, description="Limit execution price.")
    stop_price: Optional[float] = Field(default=None, description="Stop trigger price.")
    side: OrderSide = Field(..., description="Direction (BUY or SELL).")
    order_type: OrderType = Field(..., description="Order type (LIMIT, MARKET, etc.).")
    time_in_force: OrderTimeInForce = Field(default=OrderTimeInForce.GTC, description="Time-in-force constraint.")
    leverage: float = Field(default=1.0, description="Leverage setting.")
    margin_required: float = Field(default=0.0, description="Margin allocation requirements.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Request generation time.")

    # Advanced Order Fields
    oco_stop_price: Optional[float] = Field(default=None, description="Trigger price for secondary OCO leg.")
    bracket_stop_loss: Optional[float] = Field(default=None, description="Take profit limit price for brackets.")
    bracket_take_profit: Optional[float] = Field(default=None, description="Stop loss price for brackets.")
    trailing_stop_activation_price: Optional[float] = Field(default=None, description="Trigger for trailing activation.")
    trailing_stop_callback_rate: Optional[float] = Field(default=None, description="Callback rate percentage for trailing stop.")
    iceberg_display_quantity: Optional[float] = Field(default=None, description="Visible slice quantity for Iceberg order.")
    execution_flags: List[str] = Field(default_factory=list, description="Specific constraints (e.g. POST_ONLY, REDUCE_ONLY).")

    model_config = ConfigDict(frozen=True)


class Order(BaseModel):
    """Immutable model representing a broker-level execution order."""

    client_order_id: str = Field(..., description="Globally unique local client-side identifier.")
    execution_id: str = Field(..., description="Audit trace: execution workflow UUID.")
    request_id: str = Field(..., description="Audit trace: source position sizing result UUID.")
    signal_id: str = Field(..., description="Audit trace: signal identifier.")
    strategy_id: str = Field(..., description="Audit trace: strategy identifier.")
    position_id: str = Field(..., description="Audit trace: position tracker identifier.")
    correlation_id: str = Field(..., description="Correlation ID for tracing.")
    broker_order_id: Optional[str] = Field(default=None, description="Identifier assigned by exchange/broker.")
    symbol: str = Field(..., description="Ticker symbol.")
    side: OrderSide = Field(..., description="BUY or SELL.")
    order_type: OrderType = Field(..., description="LIMIT, MARKET, etc.")
    quantity: float = Field(..., description="Order size.")
    price: Optional[float] = Field(default=None, description="Limit order price.")
    stop_price: Optional[float] = Field(default=None, description="Trigger stop price.")
    time_in_force: OrderTimeInForce = Field(..., description="TIF parameter.")
    state: OrderState = Field(default=OrderState.CREATED, description="Active FSM state.")
    filled_quantity: float = Field(default=0.0, description="Accumulated filled size.")
    average_fill_price: Optional[float] = Field(default=None, description="Weighted average fill price.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Order created timestamp.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last modified time.")
    error_message: Optional[str] = Field(default=None, description="Details if order was rejected or failed.")

    # Advanced Order Fields
    oco_stop_price: Optional[float] = Field(default=None, description="Trigger price for secondary OCO leg.")
    bracket_stop_loss: Optional[float] = Field(default=None, description="Take profit limit price for brackets.")
    bracket_take_profit: Optional[float] = Field(default=None, description="Stop loss price for brackets.")
    trailing_stop_activation_price: Optional[float] = Field(default=None, description="Trigger for trailing activation.")
    trailing_stop_callback_rate: Optional[float] = Field(default=None, description="Callback rate percentage.")
    iceberg_display_quantity: Optional[float] = Field(default=None, description="Visible slice quantity.")
    execution_flags: List[str] = Field(default_factory=list, description="Specific constraints.")

    model_config = ConfigDict(frozen=True)


class OrderFill(BaseModel):
    """Immutable model representing an execution order fill event."""

    fill_id: str = Field(..., description="Unique fill transaction identifier.")
    order_id: str = Field(..., description="Broker/exchange order ID.")
    client_order_id: str = Field(..., description="Local order identifier.")
    execution_id: str = Field(..., description="Audit trace: execution workflow UUID.")
    correlation_id: str = Field(..., description="Audit trace correlation identifier.")
    symbol: str = Field(..., description="Ticker symbol.")
    quantity: float = Field(..., description="Filled size for this trade.")
    price: float = Field(..., description="Trade fill execution price.")
    commission: float = Field(..., description="Transaction fee charged.")
    fee_currency: str = Field(default="USD", description="Currency of transaction fee.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Fill timestamp.")

    model_config = ConfigDict(frozen=True)


class ExecutionMetrics(BaseModel):
    """Immutable metrics object detailing execution latencies and slippage."""

    execution_id: str = Field(..., description="Target execution UUID.")
    correlation_id: str = Field(..., description="Audit correlation identifier.")
    queue_time_ms: float = Field(default=0.0, description="Time spent waiting in execution queue.")
    validation_time_ms: float = Field(default=0.0, description="Pre-trade validation processing time.")
    network_latency_ms: float = Field(default=0.0, description="Network transmission round-trip delay.")
    broker_latency_ms: float = Field(default=0.0, description="Exchange order submission processing delay.")
    fill_latency_ms: float = Field(default=0.0, description="Delay between order submission and execution fill.")
    execution_duration_ms: float = Field(default=0.0, description="Total execution workflow processing time.")
    slippage: float = Field(default=0.0, description="Deviation between target price and final average fill price.")
    commission: float = Field(default=0.0, description="Total transaction fees incurred.")
    funding: float = Field(default=0.0, description="Mock leverage funding fees.")
    retry_count: int = Field(default=0, description="Number of execution submission retries.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Calculated timestamp.")

    model_config = ConfigDict(frozen=True)


class ExecutionJournalEntry(BaseModel):
    """Immutable entry in the sequential append-only Execution Journal."""

    journal_sequence_number: int = Field(..., description="Auto-incrementing journal sequence.")
    execution_id: str = Field(..., description="Target execution workflow UUID.")
    correlation_id: str = Field(..., description="Audit correlation identifier.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Journal log time.")
    previous_state: Optional[OrderState] = Field(..., description="FSM state before transition.")
    new_state: OrderState = Field(..., description="FSM state after transition.")
    reason: str = Field(..., description="Context description for state transition.")
    broker_response: Optional[str] = Field(default=None, description="Raw exchange/broker log response.")
    metrics: Optional[ExecutionMetrics] = Field(default=None, description="Optional execution performance metrics.")

    model_config = ConfigDict(frozen=True)


class ExecutionHealthSnapshot(BaseModel):
    """Immutable snapshot detailing health status of the execution engine subsystem."""

    broker_connectivity: str = Field(..., description="Connection status (CONNECTED, DISCONNECTED, RECONNECTING).")
    heartbeat_ok: bool = Field(..., description="True if latest heartbeat ping succeeded.")
    queue_size: int = Field(..., description="Current count of orders in priority queue.")
    pending_executions: int = Field(..., description="Count of orders in QUEUED or SUBMITTED state.")
    average_latency_ms: float = Field(..., description="Rolling average broker submission latency.")
    rejections: int = Field(..., description="Count of rejected orders.")
    timeouts: int = Field(..., description="Count of operation timeouts.")
    retry_rate: float = Field(..., description="Ratio of retry events to total orders.")
    paper_broker_status: str = Field(..., description="Paper broker operational status.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Snapshot timestamp.")

    model_config = ConfigDict(frozen=True)


class ExecutionResult(BaseModel):
    """Immutable result model summarizing final outcome of an execution request."""

    execution_id: str = Field(..., description="Target execution workflow UUID.")
    request_id: str = Field(..., description="Originating PositionSizingResult UUID.")
    correlation_id: str = Field(..., description="Audit correlation identifier.")
    status: ExecutionStatus = Field(..., description="Execution status (EXECUTED, FAILED, etc.).")
    orders: List[Order] = Field(default_factory=list, description="List of all placed broker orders.")
    metrics: Optional[ExecutionMetrics] = Field(default=None, description="Total execution metrics statistics.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Result timestamp.")

    model_config = ConfigDict(frozen=True)


class ExecutionState(BaseModel):
    """Immutable state container tracking active execution details."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    request: ExecutionRequest = Field(..., description="Active execution request.")
    orders: List[Order] = Field(default_factory=list, description="Sub-orders associated with execution.")
    result: Optional[ExecutionResult] = Field(default=None, description="Calculated final execution result.")
    journal: List[ExecutionJournalEntry] = Field(default_factory=list, description="Sequential state changes logs.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last state update.")

    model_config = ConfigDict(frozen=True)


class ExecutionSnapshot(BaseModel):
    """Consolidated snapshot tracking multiple concurrent execution workflows."""

    snapshot_id: str = Field(..., description="Unique snapshot identifier.")
    timestamp: datetime = Field(..., description="Calculation timestamp.")
    states: Dict[str, ExecutionState] = Field(default_factory=dict, description="Mapped execution states.")

    model_config = ConfigDict(frozen=True)


# ── Sprint 8: Institutional OMS & EMS Models ──────────────────────────────


class OrderIntent(BaseModel):
    """Pre-trade intent capturing the strategy's desire to execute.

    This is the primary input object into the OMS. It is created from a
    PositionSizingResult and carries all the context the OMS needs to
    validate, approve, route, and execute.
    """

    intent_id: str = Field(..., description="Globally unique intent identifier.")
    execution_id: str = Field(..., description="Execution workflow UUID.")
    request_id: str = Field(..., description="Originating PositionSizingResult UUID.")
    signal_id: str = Field(..., description="Upstream signal identifier.")
    strategy_id: str = Field(..., description="Upstream strategy identifier.")
    position_id: str = Field(..., description="Target position tracker identifier.")
    correlation_id: str = Field(..., description="End-to-end audit correlation ID.")
    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    side: OrderSide = Field(..., description="Direction (BUY or SELL).")
    order_type: OrderType = Field(..., description="Desired order type.")
    algorithm: ExecutionAlgorithmType = Field(
        default=ExecutionAlgorithmType.DIRECT,
        description="EMS execution algorithm to use.",
    )
    quantity: float = Field(..., description="Target quantity to execute.")
    price: Optional[float] = Field(default=None, description="Limit execution price.")
    stop_price: Optional[float] = Field(default=None, description="Stop trigger price.")
    time_in_force: OrderTimeInForce = Field(default=OrderTimeInForce.GTC, description="Time-in-force.")
    leverage: float = Field(default=1.0, description="Leverage setting.")
    margin_required: float = Field(default=0.0, description="Margin allocation.")

    # Bracket / OCO / Iceberg parameters
    bracket_stop_loss: Optional[float] = Field(default=None, description="Bracket SL price.")
    bracket_take_profit: Optional[float] = Field(default=None, description="Bracket TP price.")
    oco_stop_price: Optional[float] = Field(default=None, description="OCO secondary trigger.")
    trailing_stop_callback_rate: Optional[float] = Field(default=None, description="Trailing stop callback %.")
    iceberg_display_quantity: Optional[float] = Field(default=None, description="Iceberg visible slice.")
    execution_flags: List[str] = Field(default_factory=list, description="POST_ONLY, REDUCE_ONLY, etc.")

    # Algorithm-specific parameters
    algo_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Algorithm-specific configuration (e.g. duration_seconds, participation_rate).",
    )

    # OMS state tracking
    state: IntentState = Field(default=IntentState.CREATED, description="Current OMS lifecycle state.")
    child_order_ids: List[str] = Field(default_factory=list, description="Generated child order IDs.")
    rejection_reasons: List[str] = Field(default_factory=list, description="Reasons if rejected.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation time.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update.")

    model_config = ConfigDict(frozen=True)


class RoutingDecision(BaseModel):
    """Records which broker venue was selected and why."""

    decision_id: str = Field(..., description="Unique routing decision identifier.")
    intent_id: str = Field(..., description="Parent intent identifier.")
    execution_id: str = Field(..., description="Execution workflow UUID.")
    correlation_id: str = Field(..., description="Audit correlation ID.")
    broker_id: str = Field(..., description="Selected broker adapter identifier.")
    strategy: RoutingStrategy = Field(default=RoutingStrategy.DIRECT, description="Routing approach.")
    estimated_fee: float = Field(default=0.0, description="Estimated transaction fee.")
    estimated_slippage: float = Field(default=0.0, description="Estimated slippage cost.")
    estimated_latency_ms: float = Field(default=0.0, description="Expected execution latency.")
    reason: str = Field(default="", description="Human-readable selection rationale.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Decision time.")

    model_config = ConfigDict(frozen=True)


class ExecutionAlgorithmState(BaseModel):
    """Tracks progress of an algorithmic execution (TWAP, VWAP, Iceberg, POV)."""

    algo_id: str = Field(..., description="Unique algorithm execution identifier.")
    intent_id: str = Field(..., description="Parent intent identifier.")
    execution_id: str = Field(..., description="Execution workflow UUID.")
    correlation_id: str = Field(..., description="Audit correlation ID.")
    algorithm: ExecutionAlgorithmType = Field(..., description="Algorithm type.")
    total_quantity: float = Field(..., description="Total quantity to execute.")
    filled_quantity: float = Field(default=0.0, description="Quantity filled so far.")
    remaining_quantity: float = Field(default=0.0, description="Quantity remaining.")
    total_slices: int = Field(default=0, description="Total number of planned slices.")
    completed_slices: int = Field(default=0, description="Slices executed so far.")
    active_slice_order_id: Optional[str] = Field(default=None, description="Currently active child order ID.")
    average_fill_price: Optional[float] = Field(default=None, description="Running VWAP of all fills.")
    progress_pct: float = Field(default=0.0, description="Execution progress percentage (0-100).")
    is_complete: bool = Field(default=False, description="True if algorithm has finished.")
    is_cancelled: bool = Field(default=False, description="True if cancelled mid-execution.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Algorithm-specific parameters.")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Start time.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update.")

    model_config = ConfigDict(frozen=True)


class ExecutionSlice(BaseModel):
    """Individual child order slice generated by an execution algorithm."""

    slice_id: str = Field(..., description="Unique slice identifier.")
    algo_id: str = Field(..., description="Parent algorithm execution ID.")
    intent_id: str = Field(..., description="Original intent ID.")
    execution_id: str = Field(..., description="Execution workflow UUID.")
    slice_index: int = Field(..., description="Zero-based index of this slice.")
    quantity: float = Field(..., description="Slice quantity to execute.")
    price: Optional[float] = Field(default=None, description="Slice limit price.")
    scheduled_at: Optional[datetime] = Field(default=None, description="When this slice should fire.")
    child_order_id: Optional[str] = Field(default=None, description="Generated child order ID once submitted.")
    is_submitted: bool = Field(default=False, description="True if child order was submitted.")
    is_filled: bool = Field(default=False, description="True if child order filled.")
    fill_price: Optional[float] = Field(default=None, description="Actual fill price.")
    fill_quantity: float = Field(default=0.0, description="Actual filled quantity.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation time.")

    model_config = ConfigDict(frozen=True)


class OMSConfig(BaseModel):
    """Operational configuration for the OMS subsystem."""

    mode: OMSMode = Field(default=OMSMode.PAPER, description="Operating mode.")
    default_broker_id: str = Field(default="paper", description="Default broker adapter.")
    default_algorithm: ExecutionAlgorithmType = Field(
        default=ExecutionAlgorithmType.DIRECT, description="Default execution algorithm.",
    )
    default_routing: RoutingStrategy = Field(default=RoutingStrategy.DIRECT, description="Default routing strategy.")
    max_open_orders: int = Field(default=100, description="Maximum concurrent open orders.")
    max_open_intents: int = Field(default=50, description="Maximum concurrent active intents.")
    enable_recovery: bool = Field(default=True, description="Enable crash recovery reconciliation.")
    recovery_snapshot_interval_s: float = Field(default=30.0, description="Seconds between OMS snapshots.")
    intent_timeout_seconds: float = Field(default=300.0, description="Intent expiry if not completed.")

    model_config = ConfigDict(frozen=True)


class OMSState(BaseModel):
    """Immutable snapshot of the OMS subsystem operational counters."""

    total_intents: int = Field(default=0, description="All-time intent count.")
    active_intents: int = Field(default=0, description="Currently open intents.")
    completed_intents: int = Field(default=0, description="Successfully completed intents.")
    rejected_intents: int = Field(default=0, description="Rejected intents.")
    failed_intents: int = Field(default=0, description="Failed intents.")
    cancelled_intents: int = Field(default=0, description="Cancelled intents.")
    recovering_intents: int = Field(default=0, description="Intents in recovery state.")
    total_orders: int = Field(default=0, description="Total child orders generated.")
    open_orders: int = Field(default=0, description="Currently working orders.")
    filled_orders: int = Field(default=0, description="Completely filled orders.")
    total_fills: int = Field(default=0, description="Total fill events processed.")
    total_commission: float = Field(default=0.0, description="Cumulative commission paid.")
    total_slippage: float = Field(default=0.0, description="Cumulative execution slippage.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Snapshot time.")

    model_config = ConfigDict(frozen=True)


class OrderBookLevel(BaseModel):
    """Single price level in the order book."""

    price: float = Field(..., description="Price level.")
    quantity: float = Field(..., description="Quantity at this price level.")

    model_config = ConfigDict(frozen=True)


class OrderBookSnapshot(BaseModel):
    """Real-time order book depth snapshot for market impact analysis."""

    symbol: str = Field(..., description="Ticker symbol.")
    bids: List[OrderBookLevel] = Field(default_factory=list, description="Bid side levels.")
    asks: List[OrderBookLevel] = Field(default_factory=list, description="Ask side levels.")
    mid_price: Optional[float] = Field(default=None, description="Calculated mid-price.")
    spread: Optional[float] = Field(default=None, description="Best ask - best bid spread.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Snapshot time.")

    model_config = ConfigDict(frozen=True)


class BrokerStatus(BaseModel):
    """Operational status report for a connected broker adapter."""

    broker_id: str = Field(..., description="Broker adapter identifier.")
    is_connected: bool = Field(default=False, description="True if connection is live.")
    latency_ms: float = Field(default=0.0, description="Last measured ping latency.")
    open_orders: int = Field(default=0, description="Number of working orders on this venue.")
    daily_volume: float = Field(default=0.0, description="Trading volume through this adapter today.")
    error_count: int = Field(default=0, description="Errors encountered in current session.")
    last_heartbeat: Optional[datetime] = Field(default=None, description="Last successful heartbeat time.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Status time.")

    model_config = ConfigDict(frozen=True)

