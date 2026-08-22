"""Comprehensive tests for R52 Logging & Audit Framework."""

from __future__ import annotations

import logging
import threading
import time
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestLogModels:
    def test_log_severity_values(self):
        from research_platform.logging.models import LogSeverity
        assert LogSeverity.INFO == "INFO"
        assert LogSeverity.AUDIT == "AUDIT"
        assert LogSeverity.TRADE == "TRADE"
        assert LogSeverity.PERFORMANCE == "PERFORMANCE"
        assert LogSeverity.SECURITY == "SECURITY"

    def test_log_record_defaults(self):
        from research_platform.logging.models import LogRecord, LogSeverity
        rec = LogRecord(severity=LogSeverity.INFO, component="test", message="hello")
        assert rec.severity == LogSeverity.INFO
        assert rec.component == "test"
        assert rec.message == "hello"
        assert rec.correlation_id  # auto-generated

    def test_audit_record(self):
        from research_platform.logging.models import AuditRecord
        rec = AuditRecord(action="CONFIG_UPDATE", actor="admin", success=True, change_summary="Updated DB host")
        assert rec.action == "CONFIG_UPDATE"
        assert rec.success is True

    def test_trade_log_record(self):
        from research_platform.logging.models import TradeLogRecord
        rec = TradeLogRecord(order_id="ORD-001", side="BUY", symbol="AAPL",
                             quantity=100.0, price=150.25, status="FILLED")
        assert rec.order_id == "ORD-001"
        assert rec.symbol == "AAPL"
        assert rec.price == 150.25

    def test_perf_record(self):
        from research_platform.logging.models import PerfRecord
        rec = PerfRecord(operation="order_submission", duration_ms=12.5, cpu_pct=3.2, memory_mb=120.0)
        assert rec.duration_ms == 12.5
        assert rec.cpu_pct == 3.2


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

class TestFormatter:
    def test_json_formatter_output(self):
        from research_platform.logging.formatter import StructuredJsonFormatter
        import json
        fmt = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test.logger", level=logging.INFO,
            pathname="test.py", lineno=10,
            msg="test message", args=(), exc_info=None
        )
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "test message"
        assert parsed["severity"] == "INFO"

    def test_json_formatter_with_extra(self):
        from research_platform.logging.formatter import StructuredJsonFormatter
        import json
        fmt = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.DEBUG,
            pathname="test.py", lineno=5,
            msg="extra test", args=(), exc_info=None
        )
        record.correlation_id = "corr-123"
        record.extra_data = {"key": "value"}
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["correlation_id"] == "corr-123"
        assert parsed["extra_data"]["key"] == "value"


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------

class TestRotation:
    def test_create_rotating_handler(self, tmp_path):
        from research_platform.logging.rotation import create_rotating_file_handler
        handler = create_rotating_file_handler(str(tmp_path), "test.log")
        assert handler is not None
        handler.close()

    def test_create_timed_rotating_handler(self, tmp_path):
        from research_platform.logging.rotation import create_timed_rotating_handler
        handler = create_timed_rotating_handler(str(tmp_path), "test_timed.log")
        assert handler is not None
        handler.close()

    def test_creates_log_directory(self, tmp_path):
        from research_platform.logging.rotation import create_rotating_file_handler
        import os
        new_dir = str(tmp_path / "subdir" / "logs")
        handler = create_rotating_file_handler(new_dir, "test.log")
        assert os.path.isdir(new_dir)
        handler.close()


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

class TestRetention:
    def test_prune_old_files(self, tmp_path):
        from research_platform.logging.retention import RetentionPolicy
        import os, time as tm
        # Create a file and set mtime to > 91 days ago
        f = tmp_path / "old.log"
        f.write_text("old content")
        old_time = tm.time() - (91 * 86400)
        os.utime(str(f), (old_time, old_time))

        policy = RetentionPolicy(str(tmp_path), max_age_days=90)
        deleted = policy.prune()
        assert deleted == 1
        assert not f.exists()

    def test_recent_files_not_pruned(self, tmp_path):
        from research_platform.logging.retention import RetentionPolicy
        f = tmp_path / "recent.log"
        f.write_text("recent content")
        policy = RetentionPolicy(str(tmp_path), max_age_days=90)
        deleted = policy.prune()
        assert deleted == 0
        assert f.exists()

    def test_nonexistent_dir_returns_zero(self):
        from research_platform.logging.retention import RetentionPolicy
        policy = RetentionPolicy("/nonexistent/path/logs", max_age_days=90)
        deleted = policy.prune()
        assert deleted == 0


# ---------------------------------------------------------------------------
# TOJILogger
# ---------------------------------------------------------------------------

class TestTOJILogger:
    def test_logger_instantiation(self):
        from research_platform.logging.logger import TOJILogger
        logger = TOJILogger("test_component")
        assert logger.component == "test_component"

    def test_log_levels(self):
        from research_platform.logging.logger import TOJILogger
        from research_platform.logging.models import LogSeverity
        logger = TOJILogger("test")
        # Should not raise
        logger.debug("debug msg")
        logger.info("info msg")
        logger.warning("warning msg")
        logger.error("error msg")
        logger.critical("critical msg")

    def test_log_with_correlation_id(self):
        from research_platform.logging.logger import TOJILogger
        from research_platform.logging.models import LogSeverity
        logger = TOJILogger("test")
        logger.log(LogSeverity.INFO, "test", "message", correlation_id="corr-999", data={"k": "v"})

    def test_thread_safe_logging(self):
        from research_platform.logging.logger import TOJILogger
        logger = TOJILogger("thread_test")
        errors = []

        def log_worker():
            try:
                for _ in range(50):
                    logger.info("concurrent message")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=log_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------

class TestAuditLogger:
    def test_log_audit_record(self):
        from research_platform.logging.audit_logger import AuditLogger
        from research_platform.logging.models import AuditRecord
        logger = AuditLogger()
        rec = AuditRecord(action="STRATEGY_DEPLOYED", actor="operator", success=True, change_summary="v2")
        logger.log_audit(rec)  # Should not raise

    def test_record_shorthand(self):
        from research_platform.logging.audit_logger import AuditLogger
        logger = AuditLogger()
        logger.record("CONFIG_RELOAD", success=True, summary="Hot-reloaded config")

    def test_failure_record(self):
        from research_platform.logging.audit_logger import AuditLogger
        logger = AuditLogger()
        logger.record("DB_CONNECT", success=False, summary="Timeout after 5s")


# ---------------------------------------------------------------------------
# TradeLogger
# ---------------------------------------------------------------------------

class TestTradeLogger:
    def test_log_trade(self):
        from research_platform.logging.trade_logger import TradeLogger
        from research_platform.logging.models import TradeLogRecord
        logger = TradeLogger()
        rec = TradeLogRecord(order_id="T001", side="BUY", symbol="GOOG",
                             quantity=10.0, price=2800.0, status="FILLED")
        logger.log_trade(rec)

    def test_record_order(self):
        from research_platform.logging.trade_logger import TradeLogger
        logger = TradeLogger()
        logger.record_order("T002", "SELL", "MSFT", 50.0, 380.0, "PENDING")

    def test_concurrent_trade_logging(self):
        from research_platform.logging.trade_logger import TradeLogger
        logger = TradeLogger()
        errors = []

        def log_trade(i):
            try:
                logger.record_order(f"T{i:04d}", "BUY", "AAPL", float(i), 150.0, "FILLED")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=log_trade, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


# ---------------------------------------------------------------------------
# RuntimeLogger
# ---------------------------------------------------------------------------

class TestRuntimeLogger:
    def test_tick(self):
        from research_platform.logging.runtime_logger import RuntimeLogger
        logger = RuntimeLogger()
        logger.tick("strategy_loop", 1, 12.5)

    def test_loop_error(self):
        from research_platform.logging.runtime_logger import RuntimeLogger
        logger = RuntimeLogger()
        logger.loop_error("market_loop", "Connection timeout")

    def test_status_change(self):
        from research_platform.logging.runtime_logger import RuntimeLogger
        logger = RuntimeLogger()
        logger.status_change("risk_loop", "RUNNING", "PAUSED")


# ---------------------------------------------------------------------------
# SystemLogger
# ---------------------------------------------------------------------------

class TestSystemLogger:
    def test_boot_events(self):
        from research_platform.logging.system_logger import SystemLogger
        logger = SystemLogger()
        logger.boot_started()
        logger.plugin_registered("ConfigPlugin")
        logger.boot_complete(plugin_count=5)

    def test_shutdown_events(self):
        from research_platform.logging.system_logger import SystemLogger
        logger = SystemLogger()
        logger.shutdown_started()
        logger.shutdown_complete()

    def test_error(self):
        from research_platform.logging.system_logger import SystemLogger
        logger = SystemLogger()
        logger.error("Unexpected failure", error="NullPointerException")


# ---------------------------------------------------------------------------
# DatabaseLogger
# ---------------------------------------------------------------------------

class TestDatabaseLogger:
    def test_query_log(self):
        from research_platform.logging.database_logger import DatabaseLogger
        logger = DatabaseLogger()
        logger.query("SELECT", "positions", 2.5)

    def test_connection_error(self):
        from research_platform.logging.database_logger import DatabaseLogger
        logger = DatabaseLogger()
        logger.connection_error("localhost:5432", "Connection refused")

    def test_reconnected(self):
        from research_platform.logging.database_logger import DatabaseLogger
        logger = DatabaseLogger()
        logger.reconnected("localhost:5432")


# ---------------------------------------------------------------------------
# PerformanceLogger
# ---------------------------------------------------------------------------

class TestPerformanceLogger:
    def test_record(self):
        from research_platform.logging.performance_logger import PerformanceLogger
        logger = PerformanceLogger()
        logger.record("order_routing", 5.3, cpu_pct=2.1, memory_mb=250.0)

    def test_zero_values(self):
        from research_platform.logging.performance_logger import PerformanceLogger
        logger = PerformanceLogger()
        logger.record("quick_op", 0.1)


# ---------------------------------------------------------------------------
# ErrorLogger
# ---------------------------------------------------------------------------

class TestErrorLogger:
    def test_capture_exception(self):
        from research_platform.logging.error_logger import ErrorLogger
        logger = ErrorLogger()
        try:
            raise ValueError("test error")
        except ValueError as e:
            logger.capture("test_component", e, context="test context")

    def test_warning(self):
        from research_platform.logging.error_logger import ErrorLogger
        logger = ErrorLogger()
        logger.warning("order_engine", "Slippage exceeded threshold")


# ---------------------------------------------------------------------------
# SecurityLogger
# ---------------------------------------------------------------------------

class TestSecurityLogger:
    def test_access_denied(self):
        from research_platform.logging.security_logger import SecurityLogger
        logger = SecurityLogger()
        logger.access_denied("admin_panel", "unknown_user", "No credentials")

    def test_suspicious_activity(self):
        from research_platform.logging.security_logger import SecurityLogger
        logger = SecurityLogger()
        logger.suspicious_activity("Unusual order frequency", details="1000 orders/sec")

    def test_auth_failure(self):
        from research_platform.logging.security_logger import SecurityLogger
        logger = SecurityLogger()
        logger.auth_failure("user123", "Wrong API key")


# ---------------------------------------------------------------------------
# LogRepository
# ---------------------------------------------------------------------------

class TestLogRepository:
    def test_save_and_retrieve_audit(self):
        from research_platform.logging.repository import LogRepository
        repo = LogRepository()
        record = {"timestamp": "2024-01-01", "action": "TEST", "actor": "SYSTEM"}
        repo.save_audit(record)
        recent = repo.get_recent_audit(10)
        assert len(recent) >= 1
        assert recent[-1]["action"] == "TEST"

    def test_save_and_retrieve_trade(self):
        from research_platform.logging.repository import LogRepository
        repo = LogRepository()
        record = {"timestamp": "2024-01-01", "order_id": "T001", "symbol": "AAPL"}
        repo.save_trade(record)
        recent = repo.get_recent_trades(10)
        assert len(recent) >= 1

    def test_buffer_limit(self):
        from research_platform.logging.repository import LogRepository, MAX_IN_MEMORY
        repo = LogRepository()
        for i in range(MAX_IN_MEMORY + 50):
            repo.save_audit({"n": i})
        assert len(repo.get_recent_audit(MAX_IN_MEMORY + 100)) <= MAX_IN_MEMORY

    def test_thread_safe_saves(self):
        from research_platform.logging.repository import LogRepository
        repo = LogRepository()
        errors = []

        def save_records(n):
            try:
                for i in range(50):
                    repo.save_audit({"n": n * 1000 + i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=save_records, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestLogEvents:
    def test_audit_event_published(self):
        from research_platform.logging.events import AuditEventPublished
        ev = AuditEventPublished(action="CONFIG_UPDATE", actor="SYSTEM", success=True)
        assert ev.action == "CONFIG_UPDATE"

    def test_trade_event_published(self):
        from research_platform.logging.events import TradeEventPublished
        ev = TradeEventPublished(order_id="T001", symbol="AAPL", status="FILLED")
        assert ev.symbol == "AAPL"

    def test_error_event_published(self):
        from research_platform.logging.events import ErrorEventPublished
        ev = ErrorEventPublished(component="runtime", error_type="ValueError", message="bad value")
        assert ev.component == "runtime"
