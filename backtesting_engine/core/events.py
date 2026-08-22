"""Events for the Backtesting Engine (Sprint 7A)."""

from __future__ import annotations

from dataclasses import dataclass

from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class BacktestingEngineInitialized(BaseEvent):
    """Fired when the Backtesting Engine plugin initializes successfully."""


@dataclass(frozen=True)
class BacktestingEngineShutdown(BaseEvent):
    """Fired when the Backtesting Engine plugin shuts down cleanly."""


@dataclass(frozen=True)
class ReplayStarted(BaseEvent):
    """Fired when historical data replay starts."""


@dataclass(frozen=True)
class ReplayPaused(BaseEvent):
    """Fired when historical data replay is paused."""


@dataclass(frozen=True)
class ReplayCompleted(BaseEvent):
    """Fired when historical data replay reaches end-of-data."""


@dataclass(frozen=True)
class ReplayFailed(BaseEvent):
    """Fired when historical data replay fails."""


@dataclass(frozen=True)
class HistoricalBarReplayed(BaseEvent):
    """Fired when a single historical OHLCV bar is replayed."""


@dataclass(frozen=True)
class SimulatedOrderPlaced(BaseEvent):
    """Fired when a new order is submitted to the simulated broker."""


@dataclass(frozen=True)
class SimulatedOrderCancelled(BaseEvent):
    """Fired when an order is cancelled in the simulated broker."""


@dataclass(frozen=True)
class OrderMatched(BaseEvent):
    """Fired when an order matching engine fill occurs."""


@dataclass(frozen=True)
class TradeOpened(BaseEvent):
    """Fired when a new trade position is opened in the trade ledger."""


@dataclass(frozen=True)
class TradeClosed(BaseEvent):
    """Fired when a trade position is closed in the trade ledger."""


@dataclass(frozen=True)
class BacktestCompleted(BaseEvent):
    """Fired when a full backtest pipeline run completes."""


@dataclass(frozen=True)
class ExecutionDelayed(BaseEvent):
    """Fired when order execution is postponed due to configured latency."""


@dataclass(frozen=True)
class PartialFillGenerated(BaseEvent):
    """Fired when an order is partially filled due to liquidity limits or partial execution."""


@dataclass(frozen=True)
class ExecutionCompleted(BaseEvent):
    """Fired when an order is 100% executed."""


@dataclass(frozen=True)
class LiquidityLimited(BaseEvent):
    """Fired when available bar volume budget is exhausted for matching."""


@dataclass(frozen=True)
class ExecutionRejected(BaseEvent):
    """Fired when an order is rejected due to constraint violation."""

