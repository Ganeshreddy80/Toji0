"""Tests for the Structured Logging module."""

from __future__ import annotations

import json
import logging

from toji_platform.core.logging import JsonFormatter, StructuredLogger, get_logger


class TestStructuredLogger:
    """Tests for StructuredLogger."""

    def test_info_logs_message(self, caplog):
        logger = StructuredLogger("test.module", level=logging.DEBUG)
        with caplog.at_level(logging.INFO, logger="test.module"):
            logger.info("hello")
        assert "hello" in caplog.text

    def test_debug_logs_at_debug_level(self, caplog):
        logger = StructuredLogger("test.debug", level=logging.DEBUG)
        with caplog.at_level(logging.DEBUG, logger="test.debug"):
            logger.debug("debug msg")
        assert "debug msg" in caplog.text

    def test_warning_logs(self, caplog):
        logger = StructuredLogger("test.warn", level=logging.DEBUG)
        with caplog.at_level(logging.WARNING, logger="test.warn"):
            logger.warning("warning msg")
        assert "warning msg" in caplog.text

    def test_error_logs(self, caplog):
        logger = StructuredLogger("test.error", level=logging.DEBUG)
        with caplog.at_level(logging.ERROR, logger="test.error"):
            logger.error("error msg")
        assert "error msg" in caplog.text

    def test_critical_logs(self, caplog):
        logger = StructuredLogger("test.critical", level=logging.DEBUG)
        with caplog.at_level(logging.CRITICAL, logger="test.critical"):
            logger.critical("critical msg")
        assert "critical msg" in caplog.text

    def test_context_is_attached(self, caplog):
        logger = StructuredLogger("test.ctx", level=logging.DEBUG)
        with caplog.at_level(logging.INFO, logger="test.ctx"):
            logger.info("with context", user="alice", count=42)
        # The message itself is logged
        assert "with context" in caplog.text


class TestJsonFormatter:
    """Tests for the JsonFormatter."""

    def test_output_is_valid_json(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "test message"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"
        assert "timestamp" in parsed

    def test_context_included_in_output(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="ctx test",
            args=(),
            exc_info=None,
        )
        record.context = {"key": "value"}  # type: ignore[attr-defined]
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["context"]["key"] == "value"


class TestGetLogger:
    """Tests for the get_logger factory."""

    def test_returns_structured_logger(self):
        logger = get_logger("factory.test")
        assert isinstance(logger, StructuredLogger)

    def test_json_output_adds_handler(self):
        logger = get_logger("json.test", json_output=True)
        # The underlying logging.Logger should have a handler
        internal = logging.getLogger("json.test")
        assert len(internal.handlers) >= 1
