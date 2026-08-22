"""Tests for the Position Sizing models."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from position_sizing.core.enums import PositionSizingMethod, SizingStatus
from position_sizing.core.models import (
    PositionSize,
    PositionSizingResult,
    PositionSizingState,
    PositionSizingSnapshot,
)


def test_position_size_immutability():
    """Verify that PositionSize is immutable and validates types."""
    now = datetime.now(timezone.utc)
    size = PositionSize(
        symbol="BTCUSDT",
        timeframe="1h",
        quantity=1.5,
        lots=15.0,
        leverage=3.0,
        margin_required=50.0,
        account_risk_percent=0.01,
        capital_used=150.0,
        stop_distance=2.0,
        take_profit_distance=6.0,
        sizing_method=PositionSizingMethod.FIXED_FRACTIONAL,
        confidence=0.9,
        timestamp=now,
    )

    assert size.symbol == "BTCUSDT"
    assert size.quantity == 1.5
    assert size.sizing_method == PositionSizingMethod.FIXED_FRACTIONAL

    # Test immutability
    with pytest.raises(ValidationError):
        # Trying to update attribute will fail via Pydantic model validation on assignment if set
        # Since frozen=True, assignment is blocked by Pydantic
        size.quantity = 2.0


def test_position_sizing_result_validation():
    """Verify that PositionSizingResult handles validation correctly."""
    result = PositionSizingResult(
        success=False,
        status=SizingStatus.REJECTED,
        position_size=None,
        reasons=["Risk test rejected"],
        violations=["Drawdown limit exceeded"],
    )

    assert not result.success
    assert result.status == SizingStatus.REJECTED
    assert result.position_size is None
    assert "Drawdown limit exceeded" in result.violations


def test_position_sizing_state_validation():
    """Verify PositionSizingState validation."""
    now = datetime.now(timezone.utc)
    result = PositionSizingResult(
        success=True,
        status=SizingStatus.APPROVED,
        position_size=None,
    )
    state = PositionSizingState(
        symbol="BTCUSDT",
        timeframe="1h",
        result=result,
        updated_at=now,
    )

    assert state.symbol == "BTCUSDT"
    assert state.timeframe == "1h"
    assert state.result.success


def test_position_sizing_snapshot_validation():
    """Verify snapshot mappings."""
    now = datetime.now(timezone.utc)
    result = PositionSizingResult(
        success=True,
        status=SizingStatus.APPROVED,
        position_size=None,
    )
    state = PositionSizingState(
        symbol="BTCUSDT",
        timeframe="1h",
        result=result,
        updated_at=now,
    )
    snapshot = PositionSizingSnapshot(
        snapshot_id="snap-123",
        symbol="BTCUSDT",
        timestamp=now,
        states={"1h": state},
    )

    assert snapshot.snapshot_id == "snap-123"
    assert "1h" in snapshot.states
    assert snapshot.states["1h"].symbol == "BTCUSDT"
