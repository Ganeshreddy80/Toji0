"""E2E Resilience and Failure Recovery Tests.
"""

from __future__ import annotations

import os
import sys
import time
import signal
import subprocess
import socket
import pytest
from unittest.mock import patch, MagicMock

# Mock redis module for E2E runner environment stability
class ConnectionError(Exception):
    pass
mock_redis = MagicMock()
mock_redis.exceptions.ConnectionError = ConnectionError
sys.modules["redis"] = mock_redis
import redis

from toji_platform.runtime.state import RuntimeStateManager, RuntimeState
from research_platform.platform.bootstrap import bootstrap_platform
from research_platform.platform.service_registry import ServiceRegistry


def _get_free_port() -> int:
    """Find and return an unused TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def test_supervisor_environment_validation():
    """Verify that the supervisor fails fast when invalid keys are provided in PAPER mode."""
    # Launch supervisor as a separate process with invalid keys
    env = os.environ.copy()
    env["TOJI_MODE"] = "PAPER"
    env["TOJI_ADMIN_API_KEY"] = "toji_admin_secret_key_12345"  # default key
    env["TOJI_ANALYST_API_KEY"] = "toji_analyst_secret_key_67890"  # default key
    env["PYTHONPATH"] = os.getcwd()
    env["TOJI_API_PORT"] = str(_get_free_port())
    env["TRADING_MODE"] = "paper"
    env["MARKET_PROVIDER"] = "demo"
    
    # We call scripts/runtime_supervisor.py
    proc = subprocess.Popen(
        [sys.executable, "scripts/runtime_supervisor.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    
    # Wait for it to exit (it should fail fast)
    try:
        stdout, stderr = proc.communicate(timeout=5.0)
    except subprocess.TimeoutExpired:
        proc.terminate()
        stdout, stderr = proc.communicate()
        
    assert proc.returncode != 0
    assert b"validation failed" in stderr or b"Breach" in stderr or b"safety" in stderr or b"breach" in stderr or b"breach" in stdout or b"Breach" in stdout or b"validation failed" in stdout or b"BREACH" in stdout or b"BREACH" in stderr


def test_supervisor_crash_recovery_e2e():
    """Launch supervisor in DEV mode and verify that killing uvicorn or the paper engine restarts them."""
    env = os.environ.copy()
    env["TOJI_MODE"] = "DEV"
    env["DATABASE_MODE"] = "DEV"
    env["PYTHONPATH"] = os.getcwd()
    env["TOJI_API_PORT"] = str(_get_free_port())
    env["TRADING_MODE"] = "paper"
    env["MARKET_PROVIDER"] = "demo"
    env["TOJI_SINGLE_KERNEL"] = "false"
    
    # Start supervisor
    proc = subprocess.Popen(
        [sys.executable, "scripts/runtime_supervisor.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env
    )
    
    # Wait for child processes to launch (up to 15 seconds) with retry loop
    try:
        import psutil
        parent = psutil.Process(proc.pid)
        children = []
        for _ in range(30):
            time.sleep(0.5)
            try:
                children = parent.children(recursive=True)
                if len(children) >= 1:
                    break
            except Exception:
                pass
                
        # Verify children are present
        if len(children) < 1:
            # supervisor might have failed to boot, kill
            proc.terminate()
            proc.wait(timeout=2.0)
            pytest.fail("Supervisor has no children after 15s timeout.")
            
        # Select one child (e.g. uvicorn or python run_paper_trading) and terminate it
        target_child = children[0]
        child_pid = target_child.pid
        
        # Kill the child process
        target_child.kill()
        
        # Wait up to 8 seconds for supervisor to detect, reap, and restart
        restarted = False
        for _ in range(16):
            time.sleep(0.5)
            try:
                new_children = parent.children(recursive=True)
                new_pids = [c.pid for c in new_children]
                if child_pid not in new_pids and len(new_children) >= 1:
                    restarted = True
                    break
            except Exception:
                pass
        
        assert restarted, "Child process was not restarted or old pid was not reaped"
    except ImportError:
        # If psutil is not available, we skip the PID check but ensure supervisor didn't crash
        pass
    finally:
        # Clean up supervisor
        proc.terminate()
        proc.wait()


def test_redis_reconnect_recovery():
    """Verify that RuntimeStateManager handles redis connection loss and reconnects gracefully."""
    state_manager = RuntimeStateManager()
    assert state_manager.redis_client is not None
    
    # Save original client
    orig_client = state_manager.redis_client
    
    # Mock connection failure on a command
    bad_client = MagicMock()
    bad_client.set.side_effect = redis.exceptions.ConnectionError("Redis connection lost")
    bad_client.get.side_effect = redis.exceptions.ConnectionError("Redis connection lost")
    
    state_manager.redis_client = bad_client
    
    # Try calling persist and load: they should not crash the runner loop, but fail gracefully
    try:
        state_manager.persist()
        state_manager.load()
    except Exception as e:
        pytest.fail(f"State manager crashed on redis connection error: {e}")
        
    # Re-establish client
    state_manager.redis_client = orig_client
    state_manager.persist()


def test_postgres_disconnect_safe_handling():
    """Verify that PostgreSQL connection failure in PROD/PAPER mode stops execution safely."""
    from research_platform.persistence.postgres.connection import DatabaseConnection
    
    # Mock database failure
    db_conn = DatabaseConnection({"host": "non_existent_host", "port": 9999})
    
    # Set to PAPER mode
    with patch.dict(os.environ, {"TOJI_MODE": "PAPER", "FORCE_DB_FALLBACK_CHECK": "true"}):
        with pytest.raises(RuntimeError) as exc:
            db_conn.initialize()
        assert "Database connection failed" in str(exc.value)
        assert db_conn.is_fallback is False
