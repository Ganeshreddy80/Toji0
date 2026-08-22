"""Paper Trading Subsystem (Sprint 9A & 9B)."""

from paper_trading.broker import PaperBroker
from paper_trading.candle_builder import CandleBuilder
from paper_trading.events import (
    CandleClosed,
    FeedConnected,
    FeedDisconnected,
    FeedRecovered,
    MarketClosed,
    MarketOpened,
    MarketTickReceived,
    PaperAccountUpdated,
    PaperOrderCancelled,
    PaperOrderFilled,
    PaperOrderSubmitted,
    PaperPositionUpdated,
    PaperSessionStarted,
    PaperSessionStopped,
    PaperTradeExecuted,
)
from paper_trading.feed_manager import FeedManager
from paper_trading.heartbeat import HeartbeatMonitor
from paper_trading.market_data import MarketDataAdapter
from paper_trading.models.market_models import (
    FeedStatus,
    MarketCandle,
    MarketTick,
    OrderBookSnapshot,
)
from paper_trading.models.paper_models import (
    PaperAccount,
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
    PaperPosition,
    PaperSession,
    PaperSessionStatus,
    PaperTrade,
)
from paper_trading.orchestrator import PaperOrchestrator
from paper_trading.orderbook import OrderBookCache
from paper_trading.orders import PaperOrderEngine
from paper_trading.plugin import PaperTradingPlugin
from paper_trading.portfolio import PaperPortfolio
from paper_trading.reconnect import ReconnectionManager
from paper_trading.repository import PaperRepository
from paper_trading.scheduler import SessionScheduler
from paper_trading.session import PaperSessionManager
from paper_trading.state import PaperState
from paper_trading.tick_processor import TickProcessor
from paper_trading.validation import (
    EnduranceHarness,
    FaultInjector,
    LatencyMonitor,
    MemoryMonitor,
    MetricsCollector,
    OperationalMetrics,
    PerformanceProfiler,
    RecoveryValidator,
    ReplayValidator,
    ReportGenerator,
    ValidationReport,
)

__all__ = [
    "PaperAccount",
    "PaperPosition",
    "PaperOrder",
    "PaperTrade",
    "PaperSession",
    "PaperOrderStatus",
    "PaperSessionStatus",
    "PaperOrderSide",
    "PaperOrderType",
    "PaperBroker",
    "PaperPortfolio",
    "PaperOrderEngine",
    "PaperSessionManager",
    "PaperRepository",
    "PaperState",
    "PaperOrchestrator",
    "PaperTradingPlugin",
    "PaperOrderSubmitted",
    "PaperOrderFilled",
    "PaperOrderCancelled",
    "PaperTradeExecuted",
    "PaperPositionUpdated",
    "PaperAccountUpdated",
    "PaperSessionStarted",
    "PaperSessionStopped",
    # Sprint 9B Exports
    "MarketTick",
    "MarketCandle",
    "OrderBookSnapshot",
    "FeedStatus",
    "MarketDataAdapter",
    "FeedManager",
    "TickProcessor",
    "CandleBuilder",
    "OrderBookCache",
    "HeartbeatMonitor",
    "ReconnectionManager",
    "SessionScheduler",
    "MarketTickReceived",
    "CandleClosed",
    "FeedConnected",
    "FeedDisconnected",
    "FeedRecovered",
    "MarketOpened",
    "MarketClosed",
    # Sprint 9C Exports
    "EnduranceHarness",
    "PerformanceProfiler",
    "MemoryMonitor",
    "LatencyMonitor",
    "RecoveryValidator",
    "FaultInjector",
    "ReplayValidator",
    "OperationalMetrics",
    "MetricsCollector",
    "ValidationReport",
    "ReportGenerator",
]
