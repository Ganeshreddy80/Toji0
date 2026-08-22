"""Thread-safe Fault Injection Framework for Sprint 9C Paper Trading Validation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random
import threading
from typing import List, Optional

from paper_trading.models.market_models import MarketTick


class FaultInjector:
    """Thread-safe Fault Injector generating synthetic anomalous data and feed disruptions."""

    def __init__(self, seed: Optional[int] = 42) -> None:
        self._lock = threading.RLock()
        self._rng = random.Random(seed)

    def generate_malformed_ticks(self, symbol: str = "BTC/USDT", count: int = 5) -> List[Optional[MarketTick]]:
        """Generate a set of malformed MarketTick objects for testing rejection resilience."""
        now = datetime.now(timezone.utc)
        ticks: List[Optional[MarketTick]] = []

        with self._lock:
            # 1. Zero price tick (Pydantic validation error or processor rejection)
            try:
                ticks.append(MarketTick(symbol=symbol, price=0.0, volume=1.0, timestamp=now))
            except Exception:
                pass

            # 2. Negative volume tick
            try:
                ticks.append(MarketTick(symbol=symbol, price=50000.0, volume=-1.0, timestamp=now))
            except Exception:
                pass

            # 3. None object
            ticks.append(None)  # type: ignore

            # 4. Empty symbol tick
            try:
                ticks.append(MarketTick(symbol="", price=50000.0, volume=1.0, timestamp=now))
            except Exception:
                pass

        return ticks

    def generate_duplicate_tick(self, base_tick: MarketTick) -> MarketTick:
        """Generate an exact duplicate MarketTick with identical timestamp, price, and volume."""
        return MarketTick(
            symbol=base_tick.symbol,
            price=base_tick.price,
            volume=base_tick.volume,
            timestamp=base_tick.timestamp,
        )

    def generate_out_of_order_tick(self, symbol: str, reference_timestamp: datetime, seconds_back: float = 10.0) -> MarketTick:
        """Generate an out-of-order MarketTick with timestamp earlier than reference_timestamp."""
        past_ts = reference_timestamp - timedelta(seconds=seconds_back)
        return MarketTick(
            symbol=symbol,
            price=50000.0,
            volume=1.0,
            timestamp=past_ts,
        )

    def generate_stale_heartbeat_timestamp(self, timeout_seconds: float = 5.0) -> datetime:
        """Generate a timestamp guaranteed to trigger stale feed detection."""
        return datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds + 5.0)

    def inject_faults_into_stream(
        self,
        valid_ticks: List[MarketTick],
        fault_ratio: float = 0.2,
    ) -> List[Optional[MarketTick]]:
        """Inject duplicate and out-of-order ticks into a valid tick stream deterministically."""
        with self._lock:
            faulty_stream: List[Optional[MarketTick]] = []
            for tick in valid_ticks:
                faulty_stream.append(tick)
                if self._rng.random() < fault_ratio:
                    choice = self._rng.choice(["duplicate", "out_of_order"])
                    if choice == "duplicate":
                        faulty_stream.append(self.generate_duplicate_tick(tick))
                    else:
                        faulty_stream.append(
                            self.generate_out_of_order_tick(tick.symbol, tick.timestamp, seconds_back=5.0)
                        )
            return faulty_stream
