"""Feed Manager coordinating market data subscriptions, ticks, candles, and health (Sprint 9B)."""

from __future__ import annotations

import logging
import threading
from typing import List, Optional, Tuple

from paper_trading.candle_builder import CandleBuilder
from paper_trading.events import (
    CandleClosed,
    FeedConnected,
    FeedDisconnected,
    FeedRecovered,
    MarketTickReceived,
)
from paper_trading.heartbeat import HeartbeatMonitor
from paper_trading.market_data import MarketDataAdapter
from paper_trading.models.market_models import (
    FeedStatus,
    MarketCandle,
    MarketTick,
    OrderBookSnapshot,
)
from paper_trading.orderbook import OrderBookCache
from paper_trading.reconnect import ReconnectionManager
from paper_trading.scheduler import SessionScheduler
from paper_trading.tick_processor import TickProcessor
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class FeedManager:
    """Thread-safe Market Data Feed Manager.

    Coordinates subscriptions, tick processing, candle aggregation, order book cache,
    telemetry, and recovery.

    MUST NEVER submit orders, calculate portfolio, or execute trades.
    """

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        market_data_adapter: Optional[MarketDataAdapter] = None,
        tick_processor: Optional[TickProcessor] = None,
        candle_builder: Optional[CandleBuilder] = None,
        order_book_cache: Optional[OrderBookCache] = None,
        heartbeat_monitor: Optional[HeartbeatMonitor] = None,
        reconnection_manager: Optional[ReconnectionManager] = None,
        scheduler: Optional[SessionScheduler] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus

        self._adapter = market_data_adapter or MarketDataAdapter()
        self._tick_processor = tick_processor or TickProcessor()
        self._candle_builder = candle_builder or CandleBuilder()
        self._order_book_cache = order_book_cache or OrderBookCache()
        self._heartbeat = heartbeat_monitor or HeartbeatMonitor()
        self._reconnect_mgr = reconnection_manager or ReconnectionManager()
        self._scheduler = scheduler or SessionScheduler(event_bus=self._event_bus)

    def connect(self) -> FeedStatus:
        """Connect market data feed and emit FeedConnected event."""
        with self._lock:
            status = self._heartbeat.set_connected(True)
            self._reconnect_mgr.reset()

            if self._event_bus:
                self._event_bus.publish(FeedConnected(status=status))

            logger.info("Market Data Feed CONNECTED.")
            return status

    def disconnect(self, reason: str = "Disconnected") -> FeedStatus:
        """Disconnect market data feed and emit FeedDisconnected event."""
        with self._lock:
            status = self._heartbeat.set_connected(False)
            self._reconnect_mgr.register_disconnect()

            if self._event_bus:
                self._event_bus.publish(FeedDisconnected(status=status, reason=reason))

            logger.info("Market Data Feed DISCONNECTED: %s", reason)
            return status

    def recover(self) -> Tuple[bool, FeedStatus]:
        """Execute automated recovery workflow with exponential backoff."""
        success, delay, attempts = self._reconnect_mgr.attempt_reconnect()
        with self._lock:
            if success:
                self._heartbeat.increment_reconnect_count()
                status = self._heartbeat.set_connected(True)

                if self._event_bus:
                    self._event_bus.publish(FeedRecovered(status=status, attempts=attempts))

                logger.info("Market Data Feed RECOVERED after %d attempts.", attempts)
                return True, status
            else:
                status = self._heartbeat.get_status()
                return False, status

    def subscribe(self, symbol: str) -> None:
        """Subscribe to market data for symbol."""
        with self._lock:
            self._adapter.subscribe(symbol)

    def unsubscribe(self, symbol: str) -> None:
        """Unsubscribe from market data for symbol."""
        with self._lock:
            self._adapter.unsubscribe(symbol)
            self._tick_processor.reset_symbol_state(symbol)

    def get_subscribed_symbols(self) -> List[str]:
        """List currently subscribed symbols."""
        with self._lock:
            return self._adapter.get_subscribed_symbols()

    def process_tick(self, tick: MarketTick) -> Optional[MarketTick]:
        """Process incoming MarketTick: validate, record heartbeat, aggregate candles, publish events."""
        with self._lock:
            # 1. Validate & deduplicate tick
            valid_tick = self._tick_processor.validate_and_process(tick)
            if not valid_tick:
                return None

            # 2. Record telemetry heartbeat
            self._heartbeat.record_heartbeat(timestamp=valid_tick.timestamp)

            # 3. Publish MarketTickReceived
            if self._event_bus:
                self._event_bus.publish(MarketTickReceived(tick=valid_tick))

            # 4. Aggregate OHLCV Candles
            closed_candles = self._candle_builder.process_tick(valid_tick)
            for candle in closed_candles:
                if self._event_bus:
                    self._event_bus.publish(CandleClosed(candle=candle))

            return valid_tick

    def process_order_book(self, snapshot: OrderBookSnapshot) -> None:
        """Process incoming OrderBookSnapshot and update order book cache."""
        with self._lock:
            self._order_book_cache.update_snapshot(snapshot)

    def get_feed_status(self) -> FeedStatus:
        """Get current FeedStatus telemetry snapshot."""
        with self._lock:
            return self._heartbeat.get_status()

    def get_order_book(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """Get latest cached OrderBookSnapshot for symbol."""
        with self._lock:
            return self._order_book_cache.get_snapshot(symbol)

    def get_active_candle(self, symbol: str, timeframe: str) -> Optional[MarketCandle]:
        """Get currently active in-progress candle snapshot."""
        with self._lock:
            return self._candle_builder.get_active_candle(symbol, timeframe)

    def get_completed_candles(self, symbol: str, timeframe: str) -> List[MarketCandle]:
        """Get list of completed historical candles."""
        with self._lock:
            return self._candle_builder.get_completed_candles(symbol, timeframe)

    @property
    def scheduler(self) -> SessionScheduler:
        """Get session scheduler component."""
        return self._scheduler
