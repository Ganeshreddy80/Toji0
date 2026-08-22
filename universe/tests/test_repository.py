"""Tests for the universe repository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from universe.core.models import UniverseConfig, UniverseSnapshot
from universe.storage.repository import UniverseRepository


def _make_snapshot(scan_id: str | None = None) -> UniverseSnapshot:
    return UniverseSnapshot(
        scan_id=scan_id or f"scan_{uuid.uuid4().hex[:8]}",
        scanned_at=datetime.now(UTC),
        total_discovered=10,
        total_after_filter=8,
        tier_distribution={"S": 1, "A": 2, "B": 3, "C": 2},
    )


class TestUniverseRepository:
    """Test snapshot persistence and history management."""

    def test_save_and_load_latest(self) -> None:
        repo = UniverseRepository()
        snap = _make_snapshot("snap_001")
        repo.save_snapshot(snap)
        loaded = repo.load_latest_snapshot()
        assert loaded is not None
        assert loaded.scan_id == "snap_001"

    def test_load_latest_returns_most_recent(self) -> None:
        repo = UniverseRepository()
        repo.save_snapshot(_make_snapshot("snap_old"))
        repo.save_snapshot(_make_snapshot("snap_new"))
        loaded = repo.load_latest_snapshot()
        assert loaded.scan_id == "snap_new"

    def test_load_empty_returns_none(self) -> None:
        repo = UniverseRepository()
        assert repo.load_latest_snapshot() is None

    def test_snapshot_history(self) -> None:
        repo = UniverseRepository()
        for i in range(5):
            repo.save_snapshot(_make_snapshot(f"snap_{i}"))
        history = repo.load_snapshot_history(limit=3)
        assert len(history) == 3
        # Most recent first
        assert history[0].scan_id == "snap_4"

    def test_history_trimming(self) -> None:
        config = UniverseConfig(max_snapshot_history=3)
        repo = UniverseRepository(config=config)
        for i in range(10):
            repo.save_snapshot(_make_snapshot(f"snap_{i}"))
        assert repo.snapshot_count == 3
        latest = repo.load_latest_snapshot()
        assert latest.scan_id == "snap_9"

    def test_snapshot_count(self) -> None:
        repo = UniverseRepository()
        assert repo.snapshot_count == 0
        repo.save_snapshot(_make_snapshot())
        assert repo.snapshot_count == 1
