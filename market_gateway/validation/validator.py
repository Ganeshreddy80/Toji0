"""Data quality validation engine for verifying normalized market events."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from data.quality.analyzer import DataQualityAnalyzer
from data.schemas.market_data import (
    OHLCV,
    EconomicEvent,
    FundingRate,
    Liquidation,
    NewsEvent,
    OpenInterest,
    OrderBookSnapshot,
    Trade,
)

logger = logging.getLogger(__name__)


class MarketDataValidator:
    """Validates structural constraints, logic bounds, duplicates, and ordering on events."""

    def __init__(self, quality_analyzer: DataQualityAnalyzer | None = None) -> None:
        self._analyzer = quality_analyzer or DataQualityAnalyzer()
        # Keep track of state for sequence ordering, duplicate suppression, and gap detection
        # Key: (symbol, data_type, interval)
        self._last_timestamps: dict[tuple[str, str, str], datetime] = {}
        self._last_sequences: dict[str, int] = {}

    def validate_event(self, event_data: Any, symbol: str = "", interval: str = "") -> list[str]:
        """Validate a canonical market data object.

        Returns:
            list[str]: List of error messages (empty if verification passed).
        """
        errors: list[str] = []

        if isinstance(event_data, OHLCV):
            errors.extend(self._validate_ohlcv(event_data))
            errors.extend(self._track_sequence(event_data.symbol, "ohlcv", event_data.interval, event_data.timestamp))
        elif isinstance(event_data, Trade):
            errors.extend(self._validate_trade(event_data))
            errors.extend(self._track_sequence(event_data.symbol, "trade", "", event_data.timestamp))
        elif isinstance(event_data, OrderBookSnapshot):
            errors.extend(self._validate_order_book(event_data))
            errors.extend(self._track_sequence(event_data.symbol, "order_book", "", event_data.timestamp))
            if event_data.sequence_number is not None:
                errors.extend(self._check_sequence_number(event_data.symbol, event_data.sequence_number))
        elif isinstance(event_data, FundingRate):
            errors.extend(self._track_sequence(event_data.symbol, "funding", "", event_data.timestamp))
        elif isinstance(event_data, OpenInterest):
            errors.extend(self._track_sequence(event_data.symbol, "open_interest", "", event_data.timestamp))
        elif isinstance(event_data, Liquidation):
            errors.extend(self._track_sequence(event_data.symbol, "liquidation", "", event_data.timestamp))
        elif isinstance(event_data, NewsEvent):
            errors.extend(self._track_sequence(",".join(event_data.associated_symbols), "news", "", event_data.timestamp))
        elif isinstance(event_data, EconomicEvent):
            errors.extend(self._track_sequence(event_data.event_name, "macro", "", event_data.timestamp))

        return errors

    def _validate_ohlcv(self, bar: OHLCV) -> list[str]:
        errors: list[str] = []

        # Timezone check
        if bar.timestamp.tzinfo is None or bar.timestamp.tzinfo != UTC:
            errors.append(f"Timezone inconsistency: Timestamp {bar.timestamp} must be UTC.")

        # Logic checks
        if bar.open <= 0 or bar.high <= 0 or bar.low <= 0 or bar.close <= 0:
            errors.append("Invalid prices: Prices must be strictly positive.")
        if bar.high < bar.low:
            errors.append(f"Invalid prices: High ({bar.high}) is below Low ({bar.low}).")
        if bar.high < bar.open:
            errors.append(f"Invalid prices: High ({bar.high}) is below Open ({bar.open}).")
        if bar.high < bar.close:
            errors.append(f"Invalid prices: High ({bar.high}) is below Close ({bar.close}).")
        if bar.low > bar.open:
            errors.append(f"Invalid prices: Low ({bar.low}) is above Open ({bar.open}).")
        if bar.low > bar.close:
            errors.append(f"Invalid prices: Low ({bar.low}) is above Close ({bar.close}).")
        if bar.volume < 0:
            errors.append(f"Invalid volume: Volume ({bar.volume}) cannot be negative.")

        return errors

    def _validate_trade(self, trade: Trade) -> list[str]:
        errors: list[str] = []

        if trade.timestamp.tzinfo is None or trade.timestamp.tzinfo != UTC:
            errors.append(f"Timezone inconsistency: Timestamp {trade.timestamp} must be UTC.")
        if trade.price <= 0:
            errors.append(f"Invalid price: Price ({trade.price}) must be positive.")
        if trade.amount <= 0:
            errors.append(f"Invalid amount: Amount ({trade.amount}) must be positive.")
        if trade.side not in ("buy", "sell"):
            errors.append(f"Invalid side: Side ({trade.side}) must be 'buy' or 'sell'.")

        return errors

    def _validate_order_book(self, ob: OrderBookSnapshot) -> list[str]:
        errors: list[str] = []

        if ob.timestamp.tzinfo is None or ob.timestamp.tzinfo != UTC:
            errors.append(f"Timezone inconsistency: Timestamp {ob.timestamp} must be UTC.")

        for idx, (p, q) in enumerate(ob.bids):
            if p <= 0 or q < 0:
                errors.append(f"Invalid bid at index {idx}: price={p}, depth={q}")
        for idx, (p, q) in enumerate(ob.asks):
            if p <= 0 or q < 0:
                errors.append(f"Invalid ask at index {idx}: price={p}, depth={q}")

        # Check spread crossing
        if ob.bids and ob.asks:
            best_bid = ob.bids[0][0]
            best_ask = ob.asks[0][0]
            if best_bid > best_ask:
                errors.append(f"Invalid order book: Best bid ({best_bid}) crossed Best ask ({best_ask}).")

        return errors

    def _track_sequence(self, symbol: str, data_type: str, interval: str, timestamp: datetime) -> list[str]:
        errors: list[str] = []
        key = (symbol, data_type, interval)

        # Force timezone comparison safety
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        last_ts = self._last_timestamps.get(key)
        if last_ts is not None:
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=UTC)

            if timestamp < last_ts:
                errors.append(f"Sequence ordering violation: Timestamp {timestamp} is prior to last seen {last_ts}.")
            elif timestamp == last_ts:
                errors.append(f"Duplicate event: Timestamp {timestamp} already processed.")
            else:
                # Check for gap interval for candles
                if data_type == "ohlcv" and interval:
                    expected_delta = self._get_interval_delta(interval)
                    if expected_delta and (timestamp - last_ts) > expected_delta:
                        # Log/Warn instead of raising error directly so flow is not interrupted
                        logger.warning("Missing timestamps: Gap detected between %s and %s for %s", last_ts, timestamp, symbol)

        self._last_timestamps[key] = timestamp
        return errors

    def _check_sequence_number(self, symbol: str, seq: int) -> list[str]:
        errors: list[str] = []
        last_seq = self._last_sequences.get(symbol)
        if last_seq is not None:
            if seq <= last_seq:
                errors.append(f"Sequence ordering violation: Sequence number {seq} is not greater than last {last_seq}.")
        self._last_sequences[symbol] = seq
        return errors

    def _get_interval_delta(self, interval: str) -> timedelta | None:
        unit = interval[-1].lower()
        try:
            val = int(interval[:-1])
        except ValueError:
            return None

        if unit == "m":
            return timedelta(minutes=val)
        elif unit == "h":
            return timedelta(hours=val)
        elif unit == "d":
            return timedelta(days=val)
        return None
