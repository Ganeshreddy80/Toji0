"""Binance Demo connection gateway simulating WebSocket futures tick streams."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, List, Optional

from toji_platform.core.event_bus.events import MarketDataReceived
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class BinanceDemoGateway:
    """Simulates a live connection to Binance Futures API WebSocket."""

    def __init__(self, event_bus: IEventBus, symbols: List[str]) -> None:
        self.event_bus = event_bus
        self.symbols = symbols
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the simulated websocket tick stream thread."""
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Binance Demo Gateway started for symbols: %s", self.symbols)

    def stop(self) -> None:
        """Stop the tick stream thread."""
        self.running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Binance Demo Gateway stopped.")

    def _run_loop(self) -> None:
        prices = {symbol: 100.0 for symbol in self.symbols}
        prices["BTCUSDT"] = 50000.0
        prices["ETHUSDT"] = 3000.0
        btc_printed = False

        while self.running:
            for symbol in self.symbols:
                # Zero-biased random walk step: -0.05% to +0.05%
                import random
                prices[symbol] += random.uniform(-0.0005, 0.0005) * prices[symbol]
                
                if symbol == "BTCUSDT" and not btc_printed:
                    btc_printed = True
                    print(f"Exchange BTC:\n{float(prices[symbol])}\n", flush=True)
                    print(f"Binance source:\nFALSE\n", flush=True)

                # Publish event
                event = MarketDataReceived(
                    source="BinanceDemoGateway",
                    payload={
                        "symbol": symbol,
                        "price": float(prices[symbol]),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "volume": 1.5
                    }
                )
                try:
                    self.event_bus.publish(event)
                except Exception as e:
                    logger.error("Failed to publish Binance demo tick event: %s", e)
            
            if self._stop_event.wait(0.5):
                break
