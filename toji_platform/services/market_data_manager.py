"""Market Data Manager — manages subscriptions for multiple symbols.

Keeps state synchronized with the Universe Manager, supports rate limiting,
heartbeat monitoring, and reconnect triggers.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Set

from toji_platform.core.event_bus.interfaces import IEvent, IEventBus
from toji_platform.core.lifecycle.interfaces import IHealthCheck, ILifecycle
from toji_platform.core.types import HealthStatus

logger = logging.getLogger(__name__)


class MarketDataManager(ILifecycle, IHealthCheck):
    """Manages subscriptions for multiple symbols with rate limiting and health monitoring."""

    def __init__(
        self,
        event_bus: IEventBus,
        market_gateway: Any,  # Resolve from DI
        rate_limit_per_sec: float = 5.0,
        stale_threshold_sec: float = 60.0,
    ) -> None:
        self._event_bus = event_bus
        self._gateway = market_gateway
        self._rate_limit_per_sec = rate_limit_per_sec
        self._stale_threshold_sec = stale_threshold_sec

        self._subscriptions: Dict[Tuple[str, str, str], Dict[str, Any]] = {}  # Key: (symbol, sub_type, interval)
        self._lock = threading.Lock() if not hasattr(threading, "RLock") else threading.RLock()
        self._running = False
        self._shutdown_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._last_subscription_time = 0.0

    # ── ILifecycle ─────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "Market Data Manager"

    def start(self) -> None:
        """Start the heartbeat monitoring and event subscriptions."""
        if self._running:
            return
        self._running = True

        # Subscribe to asset selection and data update events
        self._event_bus.subscribe("system.asset_selected", self._on_asset_selected)
        self._event_bus.subscribe("*", self._on_wildcard_event)

        # Start the stale checker thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="MarketDataManager-Monitor"
        )
        self._monitor_thread.start()

        logger.info("Market Data Manager started ✓")

    def stop(self) -> None:
        """Stop tracking and monitoring subscriptions."""
        self._running = False
        self._shutdown_event.set()
        try:
            self._event_bus.unsubscribe("system.asset_selected", self._on_asset_selected)
            self._event_bus.unsubscribe("*", self._on_wildcard_event)
        except Exception:
            pass

        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=1.0)
            self._monitor_thread = None
        logger.info("Market Data Manager stopped ✓")

    # ── IHealthCheck ───────────────────────────────────────────────────

    def check_health(self) -> HealthStatus:
        if not self._running:
            return HealthStatus.UNHEALTHY
        
        with self._lock:
            if any(sub.get("status") == "stale" for sub in self._subscriptions.values()):
                return HealthStatus.DEGRADED
                
        return HealthStatus.HEALTHY

    # ── Public API ─────────────────────────────────────────────────────

    def subscribe(self, symbol: str, sub_type: str = "ohlcv", interval: str = "1m") -> bool:
        """Subscribe to a symbol/stream with rate limiting."""
        key = (symbol.upper(), sub_type.lower(), interval.lower())
        
        with self._lock:
            if key in self._subscriptions:
                # Already subscribed/subscribing
                return True
            
            self._subscriptions[key] = {
                "symbol": symbol,
                "sub_type": sub_type,
                "interval": interval,
                "status": "subscribing",
                "last_heartbeat": datetime.now(timezone.utc),
                "reconnect_count": 0,
            }

        # Enforce rate limiting
        self._enforce_rate_limit()

        try:
            if sub_type == "ohlcv":
                self._gateway.subscribe_candles(symbol, interval)
            elif sub_type == "trade":
                self._gateway.subscribe_trades(symbol)
            elif sub_type == "order_book":
                self._gateway.subscribe_order_book(symbol)
            else:
                raise ValueError(f"Unknown subscription type: {sub_type}")
            
            with self._lock:
                self._subscriptions[key]["status"] = "active"
                self._subscriptions[key]["last_heartbeat"] = datetime.now(timezone.utc)
            
            logger.info("Subscribed to %s %s (%s)", symbol, sub_type, interval)
            return True
        except Exception as e:
            logger.error("Failed to subscribe to %s %s (%s): %s", symbol, sub_type, interval, e)
            with self._lock:
                self._subscriptions[key]["status"] = "error"
            return False

    def unsubscribe(self, symbol: str, sub_type: str = "ohlcv", interval: str = "1m") -> None:
        """Remove a subscription from our tracked state."""
        key = (symbol.upper(), sub_type.lower(), interval.lower())
        with self._lock:
            if key in self._subscriptions:
                self._subscriptions.pop(key)
                logger.info("Unsubscribed (stopped tracking) for %s %s (%s)", symbol, sub_type, interval)

    def reconnect(self, symbol: str, sub_type: str = "ohlcv", interval: str = "1m") -> bool:
        """Force reconnect of a subscription."""
        key = (symbol.upper(), sub_type.lower(), interval.lower())
        with self._lock:
            if key in self._subscriptions:
                self._subscriptions[key]["status"] = "reconnecting"
                self._subscriptions[key]["reconnect_count"] += 1
                
        # Re-invoke subscription
        self._enforce_rate_limit()
        try:
            if sub_type == "ohlcv":
                self._gateway.subscribe_candles(symbol, interval)
            elif sub_type == "trade":
                self._gateway.subscribe_trades(symbol)
            elif sub_type == "order_book":
                self._gateway.subscribe_order_book(symbol)
            
            with self._lock:
                self._subscriptions[key]["status"] = "active"
                self._subscriptions[key]["last_heartbeat"] = datetime.now(timezone.utc)
            logger.info("Reconnected subscription for %s %s (%s)", symbol, sub_type, interval)
            return True
        except Exception as e:
            logger.error("Failed to reconnect subscription for %s %s (%s): %s", symbol, sub_type, interval, e)
            with self._lock:
                self._subscriptions[key]["status"] = "error"
            return False

    def get_subscriptions(self) -> Dict[str, Any]:
        """Return the current subscription states."""
        with self._lock:
            return {
                f"{k[0]}:{k[1]}:{k[2]}": {
                    "symbol": v["symbol"],
                    "sub_type": v["sub_type"],
                    "interval": v["interval"],
                    "status": v["status"],
                    "last_heartbeat": v["last_heartbeat"].isoformat(),
                    "reconnect_count": v["reconnect_count"],
                }
                for k, v in self._subscriptions.items()
            }

    # ── Event Handlers ─────────────────────────────────────────────────

    def _on_asset_selected(self, event: IEvent) -> None:
        """Sync subscription state when the Universe Manager selects a new asset."""
        payload = getattr(event, "payload", {}) or {}
        symbol = payload.get("symbol")
        if symbol:
            logger.info("Sync: Auto-subscribing to selected asset: %s", symbol)
            self.subscribe(symbol, "ohlcv", "1m")
            self.subscribe(symbol, "trade")

    def _on_wildcard_event(self, event: IEvent) -> None:
        """Listen to market data events to update last heartbeat."""
        event_type = getattr(event, "event_type", "")
        if event_type.startswith("system.market_"):
            payload = getattr(event, "payload", {}) or {}
            symbol = payload.get("symbol")
            if not symbol and "candle" in payload:
                symbol = payload["candle"].get("symbol")
            if not symbol and "data" in payload:
                symbol = payload["data"].get("symbol")
            
            if symbol:
                sub_type = "ohlcv"
                if "trade" in event_type:
                    sub_type = "trade"
                elif "order_book" in event_type:
                    sub_type = "order_book"
                
                # Check interval if candle event
                interval = "1m"
                if sub_type == "ohlcv":
                    candle = payload.get("candle") or payload.get("data") or {}
                    interval = candle.get("interval") or "1m"
                
                key = (symbol.upper(), sub_type, interval.lower())
                with self._lock:
                    if key in self._subscriptions:
                        self._subscriptions[key]["last_heartbeat"] = datetime.now(timezone.utc)
                        if self._subscriptions[key]["status"] in ("stale", "error"):
                            self._subscriptions[key]["status"] = "active"

    # ── Internal ───────────────────────────────────────────────────────

    def _enforce_rate_limit(self) -> None:
        """Enforce subscription rate limit."""
        delay = 1.0 / self._rate_limit_per_sec
        now = time.perf_counter()
        elapsed = now - self._last_subscription_time
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_subscription_time = time.perf_counter()

    def _monitor_loop(self) -> None:
        """Background monitor to check for stale/dead subscriptions and trigger reconnects."""
        while self._running:
            if self._shutdown_event.wait(10.0):
                break

            now = datetime.now(timezone.utc)
            stale_subs = []
            
            with self._lock:
                for key, sub in self._subscriptions.items():
                    if sub["status"] == "active":
                        elapsed = (now - sub["last_heartbeat"]).total_seconds()
                        if elapsed > self._stale_threshold_sec:
                            logger.warning(
                                "Stale subscription detected for %s %s: no update in %.1fs",
                                key[0], key[1], elapsed
                            )
                            sub["status"] = "stale"
                            stale_subs.append(key)

            # Trigger reconnect for stale subscriptions
            for key in stale_subs:
                self.reconnect(key[0], key[1], key[2])
