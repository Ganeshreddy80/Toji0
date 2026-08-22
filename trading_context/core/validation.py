"""Validation rules for the Trading Context subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from market_intelligence.core.models import MarketState
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState
from strategy.core.models import StrategyState
from trading_context.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class ContextValidator:
    """Deterministic validator to ensure completeness and alignment of upstream states."""

    @staticmethod
    def validate_states(
        symbol: str,
        timeframe: str,
        market_state: MarketState | None,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
        strategy_state: StrategyState | None,
        staleness_threshold_seconds: float = 30.0,
        expected_replay_hash: str | None = None,
    ) -> None:
        """Validate context completeness and timestamp alignment. Raises ValidationError on failure."""
        
        # 1. Presence Checks
        if market_state is None:
            raise ValidationError("Validation failed: Missing MarketState.")

        if strategy_state is None:
            raise ValidationError("Validation failed: Missing StrategyState.")

        # 2. Key Mismatch Checks
        for state_name, state in [
            ("MarketState", market_state),
            ("PatternState", pattern_state),
            ("ConfluenceState", confluence_state),
            ("StrategyState", strategy_state),
        ]:
            if state is None:
                continue

            if state.symbol != symbol:
                raise ValidationError(
                    f"Validation failed: Symbol mismatch. Context expects '{symbol}', "
                    f"but {state_name} contains '{state.symbol}'."
                )

            if state.timeframe != timeframe:
                raise ValidationError(
                    f"Validation failed: Timeframe mismatch. Context expects '{timeframe}', "
                    f"but {state_name} contains '{state.timeframe}'."
                )

        # 3. Timestamp Alignment / Staleness Checks
        timestamps: dict[str, datetime] = {
            "MarketState": market_state.updated_at,
            "StrategyState": strategy_state.updated_at,
        }
        if confluence_state is not None:
            timestamps["ConfluenceState"] = confluence_state.updated_at
        if pattern_state is not None:
            timestamps["PatternState"] = pattern_state.updated_at

        # Find min and max timestamps to calculate maximum drift
        ts_list = list(timestamps.values())
        if ts_list:
            min_ts = min(ts_list)
            max_ts = max(ts_list)
            drift = (max_ts - min_ts).total_seconds()
            if drift > staleness_threshold_seconds:
                # Detail the drift breakdown
                details = ", ".join(f"{k}={v.isoformat()}" for k, v in timestamps.items())
                raise ValidationError(
                    f"Validation failed: Stale timestamps detected. Maximum drift of {drift:.2f}s "
                    f"exceeds threshold of {staleness_threshold_seconds}s. ({details})"
                )

        # 4. Replay Hash Validation (optional)
        if expected_replay_hash is not None:
            # Generate or verify hash
            # If mismatch, raise error
            pass
