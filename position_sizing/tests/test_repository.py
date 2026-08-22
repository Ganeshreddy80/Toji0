"""Tests for the Position Sizing persistence repository."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from position_sizing.core.exceptions import RepositoryError
from position_sizing.core.enums import SizingStatus
from position_sizing.core.models import (
    PositionSizingResult,
    PositionSizingState,
    PositionSizingSnapshot,
)
from position_sizing.core.repository import PositionSizingRepository


def test_repository_in_memory_crud():
    """Verify standard CRUD operations when no DB engine is attached."""
    repo = PositionSizingRepository()

    now = datetime.now(timezone.utc)
    res = PositionSizingResult(
        success=True,
        status=SizingStatus.APPROVED,
    )
    state = PositionSizingState(
        symbol="BTCUSDT",
        timeframe="1h",
        result=res,
        updated_at=now,
    )
    snap = PositionSizingSnapshot(
        snapshot_id="snap-id",
        symbol="BTCUSDT",
        timestamp=now,
        states={"1h": state},
    )

    # Save
    repo.save_snapshot(snap)

    # Load by ID
    loaded = repo.load_snapshot("snap-id")
    assert loaded is not None
    assert loaded.symbol == "BTCUSDT"

    # Load latest
    latest = repo.load_latest_snapshot("BTCUSDT")
    assert latest is not None
    assert latest.snapshot_id == "snap-id"

    # Get historical
    history = repo.get_historical_snapshots("BTCUSDT", now, now)
    assert len(history) == 1
    assert history[0].snapshot_id == "snap-id"


def test_repository_with_postgres_storage():
    """Verify repository calls the database storage engine row write methods."""
    mock_db = MagicMock()
    repo = PositionSizingRepository(storage_engine=mock_db)

    now = datetime.now(timezone.utc)
    res = PositionSizingResult(
        success=True,
        status=SizingStatus.APPROVED,
    )
    state = PositionSizingState(
        symbol="BTCUSDT",
        timeframe="1h",
        result=res,
        updated_at=now,
    )
    snap = PositionSizingSnapshot(
        snapshot_id="snap-id",
        symbol="BTCUSDT",
        timestamp=now,
        states={"1h": state},
    )

    repo.save_snapshot(snap)

    # Verify write_rows was called on DB mock
    mock_db.write_rows.assert_called_once()
    args, kwargs = mock_db.write_rows.call_args
    assert args[0] == "position_sizing_states"
    assert args[1][0]["snapshot_id"] == "snap-id"
