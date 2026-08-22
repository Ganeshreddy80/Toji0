"""Regression test to assert that bootstrap_platform() only boots the kernel once.
"""

from __future__ import annotations

import logging
import os
import pytest
from research_platform.platform.bootstrap import bootstrap_platform
from research_platform.platform.state import PlatformState


def test_no_double_boot(caplog):
    # Reset PlatformState to a clean uninitialized state
    with PlatformState._lock:
        PlatformState._kernel = None
        
    # Capture INFO level logs
    with caplog.at_level(logging.INFO):
        app1 = bootstrap_platform()
        app2 = bootstrap_platform()
        
    assert app1 is app2
    assert PlatformState.get() is app1
    
    # Count occurrences of the boot sequence log message
    boot_msgs = [
        record.message 
        for record in caplog.records 
        if "Initializing TOJI V1 Platform Boot Sequence" in record.message
    ]
    assert len(boot_msgs) == 1, f"Expected 1 boot log, found {len(boot_msgs)}: {boot_msgs}"


def test_supervisor_api_paper_runner_boot_sequence(caplog):
    """Start supervisor, API, and PaperRunner and assert boot counter is exactly 1."""
    # 1. Reset PlatformState
    with PlatformState._lock:
        PlatformState._kernel = None

    # Enable single kernel mode environment
    os.environ["TOJI_SINGLE_KERNEL"] = "true"
    
    try:
        # Capture INFO level logs
        with caplog.at_level(logging.INFO):
            # 2. Start Supervisor Boot
            supervisor_app = bootstrap_platform()
            
            # 3. Start API (load main app module)
            from backend.main import app as fastapi_app
            
            # 4. Start PaperRunner
            from scripts.run_paper_trading import PaperRunner
            container = supervisor_app._startup.service_registry.get_service("Container")
            event_bus = supervisor_app._startup.service_registry.get_service("EventBus")
            runner = PaperRunner(container=container, event_bus=event_bus)
            
        # 5. Assert boot counter is 1
        boot_msgs = [
            record.message 
            for record in caplog.records 
            if "Initializing TOJI V1 Platform Boot Sequence" in record.message
        ]
        assert len(boot_msgs) == 1, f"Expected exactly 1 boot sequence initialization, found {len(boot_msgs)}"
    finally:
        os.environ.pop("TOJI_SINGLE_KERNEL", None)
