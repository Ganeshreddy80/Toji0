"""Session Engine for tracking Sydney, Tokyo, London, and New York trading sessions."""

from __future__ import annotations

import logging
from datetime import datetime, date, timedelta
from typing import Any

from market_intelligence.core.enums import SessionName
from market_intelligence.core.events import (
    SessionChanged,
    SessionUpdated,
    SessionBreakout,
)
from market_intelligence.core.models import SessionState
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class SessionEngine:
    """Tracks session ranges and detects transitions, overlaps, and range breakouts."""

    # Priority for active session when overlaps occur: NY > London > Tokyo > Sydney
    PRIORITY = [
        SessionName.NEW_YORK,
        SessionName.LONDON,
        SessionName.TOKYO,
        SessionName.SYDNEY,
    ]

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus
        # Mapping: (symbol, timeframe, session_name, start_date) -> SessionState
        self._sessions: dict[tuple[str, str, SessionName, date], SessionState] = {}
        # Mapping: (symbol, timeframe) -> last active session name
        self._last_active_primary: dict[tuple[str, str], SessionName | None] = {}

    def get_active_sessions_for_time(self, dt: datetime) -> list[SessionName]:
        """Determine all active sessions for a given UTC timestamp."""
        hour = dt.hour
        active = []
        # Sydney: 22:00 to 07:00 UTC
        if hour >= 22 or hour < 7:
            active.append(SessionName.SYDNEY)
        # Tokyo: 00:00 to 09:00 UTC
        if 0 <= hour < 9:
            active.append(SessionName.TOKYO)
        # London: 08:00 to 17:00 UTC
        if 8 <= hour < 17:
            active.append(SessionName.LONDON)
        # New York: 13:00 to 22:00 UTC
        if 13 <= hour < 22:
            active.append(SessionName.NEW_YORK)
        return active

    def get_session_start_date(self, name: SessionName, dt: datetime) -> date:
        """Calculate start date for a session instance, handling Sydney's midnight crossing."""
        if name == SessionName.SYDNEY:
            if dt.hour < 7:
                return (dt - timedelta(days=1)).date()
        return dt.date()

    def process_candle(self, candle: Any) -> SessionState | None:
        """Process a candle to update active sessions and evaluate range breakouts."""
        symbol = candle.symbol
        timeframe = candle.interval
        key = (symbol, timeframe)
        dt = candle.timestamp

        active_names = self.get_active_sessions_for_time(dt)
        primary_name: SessionName | None = None
        for p in self.PRIORITY:
            if p in active_names:
                primary_name = p
                break

        # 1. Update active sessions' open/high/low/close metrics
        for name in active_names:
            start_date = self.get_session_start_date(name, dt)
            session_key = (symbol, timeframe, name, start_date)

            if session_key not in self._sessions:
                # Session opened (transition)
                state = SessionState(
                    symbol=symbol,
                    session_name=name,
                    session_high=candle.high,
                    session_low=candle.low,
                    session_open=candle.open,
                    session_close=candle.close,
                    is_broken=False,
                )
                self._sessions[session_key] = state
                self._publish_changed(state, "OPEN", dt)
            else:
                # Session updated
                prev_state = self._sessions[session_key]
                state = SessionState(
                    symbol=symbol,
                    session_name=name,
                    session_high=max(prev_state.session_high, candle.high),
                    session_low=min(prev_state.session_low, candle.low),
                    session_open=prev_state.session_open,
                    session_close=candle.close,
                    is_broken=prev_state.is_broken,
                )
                self._sessions[session_key] = state
                self._publish_updated(state, dt)

        # 2. Transition checks for the primary session
        prev_primary = self._last_active_primary.get(key)
        if primary_name != prev_primary:
            self._last_active_primary[key] = primary_name
            # If a session closed
            if prev_primary is not None:
                prev_start_date = self.get_session_start_date(prev_primary, dt)
                prev_session_key = (symbol, timeframe, prev_primary, prev_start_date)
                if prev_session_key in self._sessions:
                    self._publish_changed(self._sessions[prev_session_key], "CLOSE", dt)

        # 3. Check for range breakouts of completed sessions
        # Completed sessions are those whose end hours are passed relative to the current timestamp
        for skey, state in list(self._sessions.items()):
            if state.symbol != symbol:
                continue
            # Check if this session is already closed (not active anymore)
            if state.session_name not in active_names:
                # If unbroken, check if current close breaks range
                if not state.is_broken:
                    if candle.close > state.session_high:
                        # Bullish breakout
                        new_state = SessionState(
                            symbol=symbol,
                            session_name=state.session_name,
                            session_high=state.session_high,
                            session_low=state.session_low,
                            session_open=state.session_open,
                            session_close=state.session_close,
                            is_broken=True,
                        )
                        self._sessions[skey] = new_state
                        self._publish_breakout(new_state, "BULLISH", candle)
                    elif candle.close < state.session_low:
                        # Bearish breakout
                        new_state = SessionState(
                            symbol=symbol,
                            session_name=state.session_name,
                            session_high=state.session_high,
                            session_low=state.session_low,
                            session_open=state.session_open,
                            session_close=state.session_close,
                            is_broken=True,
                        )
                        self._sessions[skey] = new_state
                        self._publish_breakout(new_state, "BEARISH", candle)

        # 4. Return the primary active session's state
        if primary_name is not None:
            primary_start_date = self.get_session_start_date(primary_name, dt)
            return self._sessions.get((symbol, timeframe, primary_name, primary_start_date))
        return None

    def get_all_sessions(self, symbol: str, timeframe: str) -> list[SessionState]:
        """Retrieve historical and active sessions for the symbol."""
        return [state for skey, state in self._sessions.items() if skey[0] == symbol and skey[1] == timeframe]

    def _publish_changed(self, state: SessionState, transition_type: str, timestamp: datetime) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": state.symbol,
            "session_name": state.session_name.value,
            "transition": transition_type,
            "timestamp": timestamp.isoformat(),
        }
        event = SessionChanged(source="market_intelligence.session_engine", payload=payload)
        self._event_bus.publish(event)

    def _publish_updated(self, state: SessionState, timestamp: datetime) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": state.symbol,
            "session_name": state.session_name.value,
            "session_high": state.session_high,
            "session_low": state.session_low,
            "session_open": state.session_open,
            "session_close": state.session_close,
            "timestamp": timestamp.isoformat(),
        }
        event = SessionUpdated(source="market_intelligence.session_engine", payload=payload)
        self._event_bus.publish(event)

    def _publish_breakout(self, state: SessionState, direction: str, candle: Any) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": state.symbol,
            "session_name": state.session_name.value,
            "direction": direction,
            "level_breached": state.session_high if direction == "BULLISH" else state.session_low,
            "candle_timestamp": candle.timestamp.isoformat(),
        }
        event = SessionBreakout(source="market_intelligence.session_engine", payload=payload)
        self._event_bus.publish(event)
