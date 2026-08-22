"""Unit tests for the Trading Context Validator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import MagicMock

from market_intelligence.core.models import MarketState
from strategy.core.models import StrategyState
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState, ConfluenceScore
from confluence.core.enums import SetupGrade
from trading_context.core.exceptions import ValidationError
from trading_context.core.validation import ContextValidator


@pytest.fixture
def base_dt() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def valid_market_state(base_dt) -> MarketState:
    return MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=base_dt,
    )


@pytest.fixture
def valid_strategy_state(base_dt) -> StrategyState:
    return StrategyState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=base_dt,
    )


@pytest.fixture
def valid_pattern_state(base_dt) -> PatternState:
    return PatternState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=base_dt,
    )


@pytest.fixture
def valid_confluence_state(base_dt) -> ConfluenceState:
    score = ConfluenceScore(
        overall_score=80.0,
        setup_grade=SetupGrade.A,
        trend_score=80.0,
        structure_score=80.0,
        liquidity_score=80.0,
        zone_score=80.0,
        volume_score=80.0,
        regime_score=80.0,
        session_score=80.0,
        mtf_score=80.0,
        correlation_score=80.0,
        pattern_score=80.0,
        quality_score=80.0,
        conflict_penalty=0.0,
    )
    return ConfluenceState(
        symbol="BTCUSDT",
        timeframe="1h",
        score=score,
        updated_at=base_dt,
    )


def test_validate_states_success(
    valid_market_state,
    valid_strategy_state,
    valid_pattern_state,
    valid_confluence_state,
):
    """Verify that a valid set of states passes validation without errors."""
    # With only required states
    ContextValidator.validate_states(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=valid_market_state,
        pattern_state=None,
        confluence_state=None,
        strategy_state=valid_strategy_state,
    )

    # With all states
    ContextValidator.validate_states(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=valid_market_state,
        pattern_state=valid_pattern_state,
        confluence_state=valid_confluence_state,
        strategy_state=valid_strategy_state,
    )


def test_validate_states_missing_required(valid_market_state, valid_strategy_state):
    """Verify validation fails if required states are missing."""
    with pytest.raises(ValidationError, match="Missing MarketState"):
        ContextValidator.validate_states(
            symbol="BTCUSDT",
            timeframe="1h",
            market_state=None,
            pattern_state=None,
            confluence_state=None,
            strategy_state=valid_strategy_state,
        )

    with pytest.raises(ValidationError, match="Missing StrategyState"):
        ContextValidator.validate_states(
            symbol="BTCUSDT",
            timeframe="1h",
            market_state=valid_market_state,
            pattern_state=None,
            confluence_state=None,
            strategy_state=None,
        )


def test_validate_states_symbol_mismatch(valid_market_state, valid_strategy_state):
    """Verify validation fails on symbol mismatches across any states."""
    # MarketState symbol mismatch
    bad_market = valid_market_state.model_copy(update={"symbol": "ETHUSDT"})
    with pytest.raises(ValidationError, match="Symbol mismatch"):
        ContextValidator.validate_states(
            symbol="BTCUSDT",
            timeframe="1h",
            market_state=bad_market,
            pattern_state=None,
            confluence_state=None,
            strategy_state=valid_strategy_state,
        )

    # StrategyState symbol mismatch
    bad_strategy = valid_strategy_state.model_copy(update={"symbol": "ETHUSDT"})
    with pytest.raises(ValidationError, match="Symbol mismatch"):
        ContextValidator.validate_states(
            symbol="BTCUSDT",
            timeframe="1h",
            market_state=valid_market_state,
            pattern_state=None,
            confluence_state=None,
            strategy_state=bad_strategy,
        )


def test_validate_states_timeframe_mismatch(valid_market_state, valid_strategy_state):
    """Verify validation fails on timeframe mismatches across any states."""
    # MarketState timeframe mismatch
    bad_market = valid_market_state.model_copy(update={"timeframe": "15m"})
    with pytest.raises(ValidationError, match="Timeframe mismatch"):
        ContextValidator.validate_states(
            symbol="BTCUSDT",
            timeframe="1h",
            market_state=bad_market,
            pattern_state=None,
            confluence_state=None,
            strategy_state=valid_strategy_state,
        )

    # StrategyState timeframe mismatch
    bad_strategy = valid_strategy_state.model_copy(update={"timeframe": "15m"})
    with pytest.raises(ValidationError, match="Timeframe mismatch"):
        ContextValidator.validate_states(
            symbol="BTCUSDT",
            timeframe="1h",
            market_state=valid_market_state,
            pattern_state=None,
            confluence_state=None,
            strategy_state=bad_strategy,
        )


def test_validate_states_stale_timestamps(valid_market_state, valid_strategy_state, base_dt):
    """Verify validation fails if the drift between states exceeds the threshold."""
    # Drift within the 30.0s threshold (e.g., 29s) should pass
    market_29s_drift = valid_market_state.model_copy(update={"updated_at": base_dt - timedelta(seconds=29)})
    ContextValidator.validate_states(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=market_29s_drift,
        pattern_state=None,
        confluence_state=None,
        strategy_state=valid_strategy_state,
        staleness_threshold_seconds=30.0,
    )

    # Drift exceeding threshold (e.g., 31s) should raise ValidationError
    market_31s_drift = valid_market_state.model_copy(update={"updated_at": base_dt - timedelta(seconds=31)})
    with pytest.raises(ValidationError, match="Stale timestamps detected"):
        ContextValidator.validate_states(
            symbol="BTCUSDT",
            timeframe="1h",
            market_state=market_31s_drift,
            pattern_state=None,
            confluence_state=None,
            strategy_state=valid_strategy_state,
            staleness_threshold_seconds=30.0,
        )


def test_validate_states_optional_states_mismatch(
    valid_market_state,
    valid_strategy_state,
    valid_pattern_state,
    valid_confluence_state,
):
    """Verify that optional states are also subject to mismatch validation."""
    # PatternState symbol mismatch
    bad_pattern = valid_pattern_state.model_copy(update={"symbol": "ETHUSDT"})
    with pytest.raises(ValidationError, match="Symbol mismatch"):
        ContextValidator.validate_states(
            symbol="BTCUSDT",
            timeframe="1h",
            market_state=valid_market_state,
            pattern_state=bad_pattern,
            confluence_state=None,
            strategy_state=valid_strategy_state,
        )

    # ConfluenceState timeframe mismatch
    bad_confluence = valid_confluence_state.model_copy(update={"timeframe": "15m"})
    with pytest.raises(ValidationError, match="Timeframe mismatch"):
        ContextValidator.validate_states(
            symbol="BTCUSDT",
            timeframe="1h",
            market_state=valid_market_state,
            pattern_state=None,
            confluence_state=bad_confluence,
            strategy_state=valid_strategy_state,
        )
