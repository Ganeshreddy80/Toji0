"""Replay Verification Framework for verifying determinism in the MIL pipeline."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from market_intelligence.core.enums import ReplayStatus
from market_intelligence.core.events import ReplayCompleted, ReplayFailed
from market_intelligence.core.exceptions import ReplayDivergenceError
from market_intelligence.core.models import MarketState, ReplayReport
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


def hash_state(state: MarketState) -> str:
    """Compute a deterministic SHA-256 hash of a MarketState snapshot, ignoring updated_at."""
    state_dict = state.model_dump(mode="json")
    state_dict.pop("updated_at", None)
    serialized = json.dumps(state_dict, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class ReplayVerifier:
    """Verifies pipeline determinism by comparing live states to historical replay states."""

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus

    def verify(
        self,
        orchestrator: Any,
        candles: list[Any],
        live_states: list[MarketState],
    ) -> ReplayReport:
        """Run replay on candle sequence, compare hashes with live states, and report findings."""
        start_time = time.perf_counter()

        symbol = candles[0].symbol if candles else ""
        total_candles = len(candles)

        # 1. Run replay using a clean replay run on the orchestrator
        replay_states = orchestrator.replay(candles)

        # 2. Compute hashes and compare
        matched = True
        divergence_at = None
        hash_live_list = []
        hash_replay_list = []

        for idx, (live_state, replay_state) in enumerate(zip(live_states, replay_states)):
            lh = hash_state(live_state)
            rh = hash_state(replay_state)
            hash_live_list.append(lh)
            hash_replay_list.append(rh)

            if lh != rh and matched:
                matched = False
                divergence_at = idx
                logger.error(
                    "Replay divergence detected at candle index %d for symbol %s.",
                    idx,
                    symbol,
                )

        # Handle size mismatches
        if len(live_states) != len(replay_states) and matched:
            matched = False
            divergence_at = min(len(live_states), len(replay_states))
            logger.error(
                "Replay divergence: state list size mismatch (live: %d, replay: %d).",
                len(live_states),
                len(replay_states),
            )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        status = ReplayStatus.PASSED if matched else ReplayStatus.FAILED

        # Hash lists representation
        hash_live = hashlib.sha256("".join(hash_live_list).encode()).hexdigest() if hash_live_list else ""
        hash_replay = hashlib.sha256("".join(hash_replay_list).encode()).hexdigest() if hash_replay_list else ""

        report = ReplayReport(
            report_id=str(uuid.uuid4()),
            symbol=symbol,
            total_candles=total_candles,
            hash_live=hash_live,
            hash_replay=hash_replay,
            matched=matched,
            divergence_at=divergence_at,
            status=status,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc),
        )

        self._publish_event(report)
        return report

    def _publish_event(self, report: ReplayReport) -> None:
        if self._event_bus is None:
            return

        if report.matched:
            event = ReplayCompleted(
                source="market_intelligence.replay_verifier",
                payload={
                    "symbol": report.symbol,
                    "total_candles": report.total_candles,
                    "matched": report.matched,
                    "duration_ms": report.duration_ms,
                },
            )
        else:
            event = ReplayFailed(
                source="market_intelligence.replay_verifier",
                payload={
                    "symbol": report.symbol,
                    "divergence_at": report.divergence_at or 0,
                    "hash_live": report.hash_live,
                    "hash_replay": report.hash_replay,
                },
            )
        self._event_bus.publish(event)
