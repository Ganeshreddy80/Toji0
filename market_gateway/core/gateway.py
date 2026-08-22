"""Central Market Gateway class serving as the single entry point for all market data."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

from data.schemas.market_data import OHLCV, OrderBookSnapshot, Trade
from market_gateway.core.events import (
    MarketCandleEvent,
    MarketOrderBookEvent,
    MarketTradeEvent,
)
from market_gateway.core.interfaces import IMarketGatewayProvider
from market_gateway.replay.engine import MarketReplayEngine
from market_gateway.router.router import MarketDataRouter
from market_gateway.validation.validator import MarketDataValidator
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from toji_platform.core.plugin_manager.interfaces import IPlugin

logger = logging.getLogger(__name__)


class MarketGateway(IPlugin):
    """Canonical Market Gateway.

    Controls provider lifecycles, maps subscription callbacks, runs data
    quality gates, dispatches events to the Event Bus, and manages replay services.
    """

    def __init__(self, event_bus: IEventBus, validator: MarketDataValidator | None = None) -> None:
        self._event_bus = event_bus
        self._validator = validator or MarketDataValidator()
        self._router = MarketDataRouter()
        self._replay_engine = MarketReplayEngine(self._event_bus, self._validator)
        self._state = ModuleState.CREATED
        self._active_subscriptions: set[tuple[str, str, str]] = set()  # (symbol, type, interval)

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("market_gateway")

    @property
    def name(self) -> str:
        return "Market Gateway"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list[PluginId]:
        return []

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Boot all registered providers and transition state to RUNNING."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Market Gateway...")

        for provider in self._router.list_providers():
            try:
                provider.initialize()
            except Exception as e:
                logger.error("Failed to initialize provider %s: %s", provider.name, e)
                self._state = ModuleState.FAILED
                raise

        self._state = ModuleState.RUNNING
        logger.info("Market Gateway running successfully ✓")

    def shutdown(self) -> None:
        """Gracefully stop and shut down all providers."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Market Gateway...")

        for provider in self._router.list_providers():
            try:
                provider.shutdown()
            except Exception as e:
                logger.error("Error shutting down provider %s: %s", provider.name, e)

        self._state = ModuleState.STOPPED
        logger.info("Market Gateway stopped successfully ✓")

    def health_check(self) -> HealthStatus:
        """Run health status check on all active providers.

        If any provider is disconnected/unhealthy, return degraded or unhealthy.
        """
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY

        providers = self._router.list_providers()
        if not providers:
            return HealthStatus.DEGRADED

        has_healthy = False
        has_unhealthy = False

        for p in providers:
            stats = p.check_health()
            status = stats.get("status", "disconnected")
            if status == "connected":
                has_healthy = True
            elif status in ("disconnected", "unhealthy"):
                has_unhealthy = True

        if has_unhealthy and not has_healthy:
            return HealthStatus.UNHEALTHY
        if has_unhealthy and has_healthy:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def get_detailed_health(self) -> dict[str, dict[str, Any]]:
        """Retrieve connection details and statistics from all providers."""
        return {p.name: p.check_health() for p in self._router.list_providers()}

    # ── Provider Registration ───────────────────────────────────────────

    def register_provider(self, provider: IMarketGatewayProvider) -> None:
        self._router.register_provider(provider)
        if hasattr(provider, "set_event_bus"):
            provider.set_event_bus(self._event_bus)

    # ── Real-Time Streaming Subscriptions ────────────────────────────────

    def _canonicalize_symbol(self, symbol: str) -> str:
        """Helper to format a raw symbol (e.g. BTCUSDT) to canonical format (BTC/USDT)."""
        if "/" in symbol:
            return symbol
        for suffix in ("USDT", "BUSD", "USD", "USDC", "BTC", "ETH"):
            if symbol.endswith(suffix):
                base = symbol[:-len(suffix)]
                if base:
                    return f"{base}/{suffix}"
        return symbol

    # ── Real-Time Streaming Subscriptions ────────────────────────────────

    def subscribe_candles(self, symbol: str, interval: str) -> None:
        """Subscribe to real-time candles for a symbol, routing to resolved provider."""
        provider = self._router.get_provider(symbol)
        clean_symbol = symbol.replace("/", "")

        def _callback(candle: OHLCV) -> None:
            # 1. Run Data Quality Gate
            errors = self._validator.validate_event(candle)
            if errors:
                logger.warning("Gateway: validation failed for candle event: %s", errors)
                return  # Skip publication of corrupt data

            canonical = self._canonicalize_symbol(candle.symbol)

            # 2. Package and Publish standard event
            event = MarketCandleEvent(
                source=f"market_gateway.{provider.name}.candle",
                payload={
                    "symbol": canonical,
                    "data_type": "ohlcv",
                    "prices": [candle.close],
                    "volumes": [candle.volume],
                    "data": {**candle.model_dump(), "symbol": canonical},
                },
            )
            self._event_bus.publish(event)

            # Publish MarketDataReceived event to kick off end-to-end integration pipeline
            from toji_platform.core.event_bus.events import MarketDataReceived
            received_event = MarketDataReceived(
                source=f"market_gateway.{provider.name}.candle",
                payload={
                    "symbol": canonical,
                    "candle": {**candle.model_dump(), "symbol": canonical},
                },
            )
            self._event_bus.publish(received_event)

        provider.subscribe_candles(clean_symbol, interval, _callback)
        self._active_subscriptions.add((symbol, "ohlcv", interval))
        logger.info("Gateway: Subscribed to candles for %s on %s", symbol, provider.name)

    def subscribe_trades(self, symbol: str) -> None:
        """Subscribe to real-time trades for a symbol, routing to resolved provider."""
        provider = self._router.get_provider(symbol)
        clean_symbol = symbol.replace("/", "")

        def _callback(trade: Trade) -> None:
            errors = self._validator.validate_event(trade)
            if errors:
                logger.warning("Gateway: validation failed for trade event: %s", errors)
                return

            canonical = self._canonicalize_symbol(trade.symbol)

            event = MarketTradeEvent(
                source=f"market_gateway.{provider.name}.trade",
                payload={
                    "symbol": canonical,
                    "data_type": "trade",
                    "prices": [trade.price],
                    "volumes": [trade.amount],
                    "data": {**trade.model_dump(), "symbol": canonical},
                },
            )
            self._event_bus.publish(event)

        provider.subscribe_trades(clean_symbol, _callback)
        self._active_subscriptions.add((symbol, "trade", ""))
        logger.info("Gateway: Subscribed to trades for %s on %s", symbol, provider.name)

    def subscribe_order_book(self, symbol: str) -> None:
        """Subscribe to L2 order book for a symbol, routing to resolved provider."""
        provider = self._router.get_provider(symbol)
        clean_symbol = symbol.replace("/", "")

        def _callback(ob: OrderBookSnapshot) -> None:
            errors = self._validator.validate_event(ob)
            if errors:
                logger.warning("Gateway: validation failed for order book snapshot: %s", errors)
                return

            canonical = self._canonicalize_symbol(ob.symbol)

            event = MarketOrderBookEvent(
                source=f"market_gateway.{provider.name}.order_book",
                payload={
                    "symbol": canonical,
                    "data_type": "order_book",
                    "data": {**ob.model_dump(), "symbol": canonical},
                },
            )
            self._event_bus.publish(event)

        provider.subscribe_order_book(clean_symbol, _callback)
        self._active_subscriptions.add((symbol, "order_book", ""))
        logger.info("Gateway: Subscribed to order book for %s on %s", symbol, provider.name)

    # ── Historical Queries ──────────────────────────────────────────────

    def get_historical_candles(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[OHLCV]:
        """Query historical candles directly via resolved provider."""
        provider = self._router.get_provider(symbol)
        clean_symbol = symbol.replace("/", "")
        candles = provider.get_historical_candles(clean_symbol, interval, start, end)
        for candle in candles:
            candle.symbol = self._canonicalize_symbol(candle.symbol)
        return candles

    # ── Replay Operations ────────────────────────────────────────────────

    @property
    def replay_engine(self) -> MarketReplayEngine:
        return self._replay_engine

    @property
    def active_subscriptions(self) -> list[tuple[str, str, str]]:
        return list(self._active_subscriptions)
