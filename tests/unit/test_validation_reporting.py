"""Unit tests for validation orchestrator reporting formatting.
"""

from __future__ import annotations

import logging
import pytest
from unittest.mock import MagicMock, patch
import io
import sys

from research_platform.validation.orchestrator import ValidationOrchestrator
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus, ValidationDuration


class MockPassChecker(IChecker):
    @property
    def name(self) -> str:
        return "DatabaseChecker"
    
    def run(self) -> CheckResult:
        return CheckResult(
            check_name="DatabaseChecker",
            status=CheckStatus.PASS,
            message="PostgreSQL healthy",
            duration_ms=45.0
        )


class MockFailChecker(IChecker):
    @property
    def name(self) -> str:
        return "MarketGatewayChecker"
    
    def run(self) -> CheckResult:
        return CheckResult(
            check_name="MarketGatewayChecker",
            status=CheckStatus.FAIL,
            message="websocket unavailable",
            duration_ms=120.0
        )


class MockWarnChecker(IChecker):
    @property
    def name(self) -> str:
        return "ThreadChecker"
    
    def run(self) -> CheckResult:
        return CheckResult(
            check_name="ThreadChecker",
            status=CheckStatus.WARN,
            message="High thread count warning",
            duration_ms=30.0
        )


def test_validation_reporting_stdout():
    """Verify that checker results print to stdout in the exact expected format."""
    checkers = [MockPassChecker(), MockFailChecker(), MockWarnChecker()]
    orchestrator = ValidationOrchestrator(checkers=checkers)

    # Capture standard output
    captured_stdout = io.StringIO()
    sys.stdout = captured_stdout

    try:
        with patch.object(orchestrator, "_publish_event"):
            orchestrator.run_all(ValidationDuration.QUICK)
    finally:
        sys.stdout = sys.__stdout__

    output = captured_stdout.getvalue()

    # Verify stdout formats
    assert "DatabaseChecker:" in output
    assert "PASS" in output
    assert "PostgreSQL healthy" in output
    assert "Duration: 0.0450s" in output

    assert "MarketGatewayChecker:" in output
    assert "FAIL" in output
    assert "Reason: websocket unavailable" in output
    assert "Duration: 0.1200s" in output

    assert "ThreadChecker:" in output
    assert "WARN" in output
    assert "High thread count warning" in output
    assert "Duration: 0.0300s" in output


def test_validation_reporting_logs():
    """Verify that the checker details and aggregate summary are sent to loggers."""
    checkers = [MockPassChecker(), MockFailChecker(), MockWarnChecker()]
    orchestrator = ValidationOrchestrator(checkers=checkers)

    with patch("research_platform.validation.orchestrator.logger") as mock_logger:
        with patch.object(orchestrator, "_publish_event"):
            orchestrator.run_all(ValidationDuration.QUICK)
            
        # Verify logger calls
        mock_logger.info.assert_any_call("Checker: %s", "DatabaseChecker")
        mock_logger.info.assert_any_call("Status: %s", "PASS")
        mock_logger.info.assert_any_call("Message: %s", "PostgreSQL healthy")
        
        mock_logger.info.assert_any_call("Checker: %s", "MarketGatewayChecker")
        mock_logger.info.assert_any_call("Status: %s", "FAIL")
        mock_logger.info.assert_any_call("Message: %s", "Reason: websocket unavailable")

        mock_logger.info.assert_any_call(
            "Validation complete: %s — %s/%s PASS, %s FAIL, %s WARN",
            "FAILED", 1, 3, 1, 1
        )
