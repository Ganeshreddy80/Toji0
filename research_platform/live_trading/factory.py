"""Factory for creating market data gateway providers based on environment variables.
"""

from __future__ import annotations

import logging
import os
from typing import Any, List

from market_gateway.providers.binance.client import BinanceGatewayProvider
from market_gateway.providers.binance.exchange import BinanceExchangeProvider
from toji_platform.core.event_bus.events import MarketDataReceived
from market_gateway.providers.binance.config import BinanceEndpointConfig

logger = logging.getLogger(__name__)


class BinanceMarketGateway:
    """Real Binance Market Data Gateway wrapper reusing the existing provider."""

    def __init__(self, event_bus: Any, symbols: List[str], container: Any) -> None:
        self.event_bus = event_bus
        self.symbols = symbols
        self.container = container
        self._provider = None
        self.running = False

        market_provider = os.getenv("MARKET_PROVIDER", "demo")
        self.endpoint_config = BinanceEndpointConfig.from_provider(market_provider)
        self.rest_url = self.endpoint_config.rest_url
        self.ws_url = self.endpoint_config.ws_url

    def start(self) -> None:
        self.running = True

        market_provider = os.getenv("MARKET_PROVIDER", "demo").lower()
        trading_mode = os.getenv("TRADING_MODE", "paper").upper()
        real_orders_status = "ENABLED" if trading_mode == "LIVE" and market_provider in ("binance_live", "binance_testnet") else "DISABLED"

        print("======== TOJI BINANCE CONFIG ========\n", flush=True)
        print(f"Market Provider:\n{market_provider.lower()}\n", flush=True)
        print(f"REST:\n{self.rest_url}\n", flush=True)
        print(f"WS:\n{self.ws_url}\n", flush=True)
        print(f"Trading:\n{trading_mode}\n", flush=True)
        print(f"Real Orders:\n{real_orders_status}\n", flush=True)
        print("====================================", flush=True)

        # Reuse or resolve the existing provider registered in the DI container
        provider = None
        if self.container.has(BinanceExchangeProvider):
            provider = self.container.resolve(BinanceExchangeProvider)
        elif self.container.has("BinanceExchangeProvider"):
            provider = self.container.resolve("BinanceExchangeProvider")

        if not provider:
            provider = BinanceGatewayProvider(use_mock=False)
            self.container.register(BinanceExchangeProvider, instance=provider)

        self._provider = provider

        # Intercept and normalize the raw MarketTickReceived events before broadcasting
        orig_publish_event = provider._publish_event
        self._btc_tick_printed = False

        def intercepted_publish_event(event_class: Any, payload: dict) -> None:
            if event_class.__name__ == "MarketTickReceived":
                symbol = payload.get("s")
                price = None
                volume = 0.0
                event_type = payload.get("e")

                if event_type == "trade":
                    price = payload.get("p")
                    volume = payload.get("q")
                elif event_type == "kline":
                    price = payload.get("k", {}).get("c")
                    volume = payload.get("k", {}).get("v")
                elif event_type in ("24hrTicker", "24hrMiniTicker"):
                    price = payload.get("c")
                else:
                    price = payload.get("price") or payload.get("c") or payload.get("p")
                    volume = payload.get("volume") or payload.get("q") or payload.get("v") or 0.0

                if symbol and price is not None:
                    try:
                        price_val = float(price)
                        volume_val = float(volume) if volume else 0.0
                    except (ValueError, TypeError):
                        price_val = 0.0
                        volume_val = 0.0

                    from datetime import datetime, timezone
                    ts_ms = payload.get("E") or payload.get("T")
                    if isinstance(ts_ms, (int, float)):
                        timestamp = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).isoformat()
                    else:
                        timestamp = datetime.now(timezone.utc).isoformat()

                    normalized_payload = {
                        "symbol": symbol,
                        "price": price_val,
                        "timestamp": timestamp,
                        "volume": volume_val
                    }

                    if symbol == "BTCUSDT" and not self._btc_tick_printed:
                        self._btc_tick_printed = True
                        is_binance_real = "stream.binance.com" in self.ws_url or "binance.vision" in self.ws_url
                        print(f"Exchange BTC:\n{price_val}\n", flush=True)
                        print(f"Binance source:\n{'TRUE' if is_binance_real else 'FALSE'}\n", flush=True)

                    norm_event = MarketDataReceived(source="BinanceMarketGateway", payload=normalized_payload)
                    self.event_bus.publish(norm_event)
                    return

            orig_publish_event(event_class, payload)

        provider._publish_event = intercepted_publish_event

        provider.use_mock = False
        provider._rest_url = self.rest_url
        provider._ws_url = self.ws_url
        provider.set_event_bus(self.event_bus)

        # Set subscription targets
        for symbol in self.symbols:
            provider.subscribe_trade_stream(symbol)

        # Initialize connection routines
        provider.initialize()
        logger.info(
            "BinanceMarketGateway initialized: rest_url=%s, ws_url=%s for symbols=%s",
            self.rest_url,
            self.ws_url,
            self.symbols,
        )

    def stop(self) -> None:
        self.running = False
        if self._provider:
            self._provider.shutdown()
            logger.info("BinanceMarketGateway connection terminated.")


class MarketProviderFactory:
    """Factory creating the decoupled market source gateways."""

    @staticmethod
    def create_provider(event_bus: Any, symbols: List[str], container: Any) -> Any:
        market_provider = os.getenv("MARKET_PROVIDER")
        if not market_provider:
            raise ValueError("MARKET_PROVIDER environment variable must be explicitly configured!")

        market_provider = market_provider.lower()
        if market_provider in ("binance_live", "binance_testnet"):
            return BinanceMarketGateway(event_bus, symbols, container)
        elif market_provider == "demo":
            from research_platform.live_trading.binance_demo import BinanceDemoGateway
            return BinanceDemoGateway(event_bus, symbols)
        else:
            raise ValueError(f"Unsupported MARKET_PROVIDER value: {market_provider}")
