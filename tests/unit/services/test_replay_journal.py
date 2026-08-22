"""Unit tests for Replay Journal service."""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import date
from pathlib import Path
import pytest
from dataclasses import dataclass

from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.events import BaseEvent
from toji_platform.services.replay_journal import ReplayJournal


@pytest.fixture
def temp_replay_dir():
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path)


def test_replay_journal_capture_and_replay(temp_replay_dir):
    bus = InMemoryEventBus()
    rj = ReplayJournal(base_dir=temp_replay_dir, event_bus=bus, flush_interval=0.1)
    rj.start()

    @dataclass(frozen=True)
    class CustomEvent(BaseEvent):
        pass

    event1 = CustomEvent(source="source1", payload={"data": "val1", "correlation_id": "sess-1"})
    event2 = CustomEvent(source="source2", payload={"data": "val2", "correlation_id": "sess-2"})

    bus.publish(event1)
    bus.publish(event2)

    rj.stop()  # Flushes buffer

    # Load and verify
    events = rj.load_events(start_date=date.today(), end_date=date.today())
    assert len(events) == 2
    assert events[0]["source"] == "source1"
    assert events[1]["source"] == "source2"
    assert events[0]["correlation_id"] == "sess-1"

    # Replay back to a fresh bus
    replay_bus = InMemoryEventBus()
    events_received = []
    
    replay_bus.subscribe("*", lambda e: events_received.append(e))
    replayed_count = rj.replay_to_bus(replay_bus)
    
    assert replayed_count == 2
    assert len(events_received) == 2
    assert events_received[0].source == "source1"
