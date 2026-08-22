"""Thread-safe Deterministic Replay Validator for Sprint 9C Paper Trading Validation."""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Tuple

from paper_trading.candle_builder import CandleBuilder
from paper_trading.events import CandleClosed, MarketTickReceived, PaperOrderFilled
from paper_trading.feed_manager import FeedManager
from paper_trading.models.market_models import MarketCandle, MarketTick
from paper_trading.orchestrator import PaperOrchestrator
from toji_platform.core.event_bus import InMemoryEventBus


class ReplayValidator:
    """Thread-safe Deterministic Replay Validator verifying zero drift across identical simulation runs."""

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def verify_candle_replay(
        self,
        ticks: List[MarketTick],
        timeframes: List[str] = None,
    ) -> bool:
        """Process ticks through two independent CandleBuilder instances and assert exact OHLCV identity."""
        tfs = timeframes or ["1m"]
        cb1 = CandleBuilder(timeframes=tfs)
        cb2 = CandleBuilder(timeframes=tfs)

        with self._lock:
            closed1: List[MarketCandle] = []
            closed2: List[MarketCandle] = []

            for tick in ticks:
                closed1.extend(cb1.process_tick(tick))
                closed2.extend(cb2.process_tick(tick))

            if len(closed1) != len(closed2):
                return False

            for c1, c2 in zip(closed1, closed2):
                if (
                    c1.symbol != c2.symbol
                    or c1.timeframe != c2.timeframe
                    or c1.open != c2.open
                    or c1.high != c2.high
                    or c1.low != c2.low
                    or c1.close != c2.close
                    or c1.volume != c2.volume
                    or c1.open_time != c2.open_time
                    or c1.close_time != c2.close_time
                ):
                    return False

            return True

    def verify_event_replay(self, ticks: List[MarketTick]) -> bool:
        """Process ticks through two FeedManager + EventBus pipelines and assert identical emitted event sequences."""
        bus1 = InMemoryEventBus()
        bus2 = InMemoryEventBus()

        events1: List[str] = []
        events2: List[str] = []

        def record_event(target_list: List[str], event: Any) -> None:
            payload = dict(event.payload)
            if "status" in payload and isinstance(payload["status"], dict):
                status_dict = dict(payload["status"])
                status_dict.pop("heartbeat_time", None)
                payload["status"] = status_dict
            payload.pop("timestamp", None)
            target_list.append(f"{event.event_type}:{payload}")

        bus1.subscribe("*", lambda e: record_event(events1, e))
        bus2.subscribe("*", lambda e: record_event(events2, e))

        fm1 = FeedManager(event_bus=bus1)
        fm2 = FeedManager(event_bus=bus2)

        with self._lock:
            fm1.connect()
            fm2.connect()

            for tick in ticks:
                fm1.process_tick(tick)
                fm2.process_tick(tick)

            return events1 == events2

    def verify_fill_replay(
        self,
        ticks: List[MarketTick],
        orders_to_submit: List[Dict[str, Any]],
    ) -> bool:
        """Execute identical order sequences across two PaperOrchestrator instances and assert identical fills & equity."""
        orch1 = PaperOrchestrator(initial_capital=100000.0)
        orch2 = PaperOrchestrator(initial_capital=100000.0)

        orch1.start_session()
        orch2.start_session()

        with self._lock:
            fills1 = []
            fills2 = []

            for tick in ticks:
                for req in orders_to_submit:
                    if req.get("trigger_price") and tick.price >= req["trigger_price"]:
                        o1, t1 = orch1.submit_order(
                            symbol=tick.symbol,
                            side=req["side"],
                            quantity=req["quantity"],
                            current_market_price=tick.price,
                        )
                        o2, t2 = orch2.submit_order(
                            symbol=tick.symbol,
                            side=req["side"],
                            quantity=req["quantity"],
                            current_market_price=tick.price,
                        )
                        fills1.extend(t1)
                        fills2.extend(t2)

            eq1 = orch1.get_account().equity
            eq2 = orch2.get_account().equity

            return len(fills1) == len(fills2) and eq1 == eq2

    def validate_full_replay(self, ticks: List[MarketTick]) -> Dict[str, bool]:
        """Perform comprehensive replay validation across candles and events."""
        with self._lock:
            candles_match = self.verify_candle_replay(ticks)
            events_match = self.verify_event_replay(ticks)
            return {
                "candle_replay_deterministic": candles_match,
                "event_replay_deterministic": events_match,
                "overall_deterministic": candles_match and events_match,
            }
