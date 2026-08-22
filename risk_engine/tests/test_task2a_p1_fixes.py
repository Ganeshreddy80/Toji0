"""Regression tests for Sprint 2 Task 2A — P1 Audit Fixes.

Verifies:
- RE_PAYLOAD_001 fail-closed guard for missing/invalid symbol, quantity, price
  in both orchestrator.process_execution_request and risk_engine.evaluate_execution_request.
- RiskDecision.REVIEW emits RiskReview (not ExecutionRejected).
- RiskDecision.BLOCK emits ExecutionRejected (not RiskReview).
- RiskDecision.ALLOW emits ExecutionApproved.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from risk_engine.core.orchestrator import RiskOrchestrator
from risk_engine.core.enums import RiskDecision, RiskSeverity
from risk_engine.core.state import RiskStateStore
from risk_engine.core.repository import RiskRepository
from risk_engine.analysis.risk_engine import RiskEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_orchestrator(event_bus=None):
    orch = RiskOrchestrator()
    orch.initialize(
        state_store=RiskStateStore(),
        repository=RiskRepository(),
        risk_engine=RiskEngine(),
        event_bus=event_bus,
    )
    return orch


def _valid_financial_payload(**overrides):
    base = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "quantity": 0.5,
        "price": 50000.0,
        "equity": 10000.0,
        "balance": 10000.0,
        "initial_balance": 10000.0,
    }
    base.update(overrides)
    return base


# ===========================================================================
# P1-A / P1-B: orchestrator.process_execution_request payload validation
# ===========================================================================

class TestPayloadValidationOrchestrator:

    def test_missing_symbol_blocks(self):
        orch = _make_orchestrator()
        payload = _valid_financial_payload()
        del payload["symbol"]
        result = orch.process_execution_request(payload)
        assert result.assessment.decision == RiskDecision.BLOCK
        assert any(v.rule_id == "RE_PAYLOAD_001" for v in result.assessment.violations)
        assert any("symbol" in v.message for v in result.assessment.violations)

    def test_empty_symbol_blocks(self):
        orch = _make_orchestrator()
        result = orch.process_execution_request(_valid_financial_payload(symbol="  "))
        assert result.assessment.decision == RiskDecision.BLOCK
        assert any(v.rule_id == "RE_PAYLOAD_001" for v in result.assessment.violations)

    def test_missing_quantity_blocks(self):
        orch = _make_orchestrator()
        payload = _valid_financial_payload()
        del payload["quantity"]
        result = orch.process_execution_request(payload)
        assert result.assessment.decision == RiskDecision.BLOCK
        assert any(v.rule_id == "RE_PAYLOAD_001" for v in result.assessment.violations)

    def test_zero_quantity_blocks(self):
        orch = _make_orchestrator()
        result = orch.process_execution_request(_valid_financial_payload(quantity=0.0))
        assert result.assessment.decision == RiskDecision.BLOCK
        assert any(v.rule_id == "RE_PAYLOAD_001" for v in result.assessment.violations)

    def test_negative_quantity_blocks(self):
        orch = _make_orchestrator()
        result = orch.process_execution_request(_valid_financial_payload(quantity=-1.0))
        assert result.assessment.decision == RiskDecision.BLOCK
        assert any(v.rule_id == "RE_PAYLOAD_001" for v in result.assessment.violations)

    def test_missing_price_blocks(self):
        orch = _make_orchestrator()
        payload = _valid_financial_payload()
        del payload["price"]
        result = orch.process_execution_request(payload)
        assert result.assessment.decision == RiskDecision.BLOCK
        assert any(v.rule_id == "RE_PAYLOAD_001" for v in result.assessment.violations)
        assert any("price" in v.message for v in result.assessment.violations)

    def test_zero_price_blocks(self):
        orch = _make_orchestrator()
        result = orch.process_execution_request(_valid_financial_payload(price=0.0))
        assert result.assessment.decision == RiskDecision.BLOCK
        assert any(v.rule_id == "RE_PAYLOAD_001" for v in result.assessment.violations)

    def test_negative_price_blocks(self):
        orch = _make_orchestrator()
        result = orch.process_execution_request(_valid_financial_payload(price=-50000.0))
        assert result.assessment.decision == RiskDecision.BLOCK
        assert any(v.rule_id == "RE_PAYLOAD_001" for v in result.assessment.violations)

    def test_no_event_published_on_payload_failure(self):
        mock_bus = MagicMock()
        orch = _make_orchestrator(event_bus=mock_bus)
        payload = _valid_financial_payload()
        del payload["price"]
        orch.process_execution_request(payload)
        mock_bus.publish.assert_not_called()

    def test_payload_violation_is_critical_severity(self):
        orch = _make_orchestrator()
        payload = _valid_financial_payload()
        del payload["symbol"]
        result = orch.process_execution_request(payload)
        v = next(v for v in result.assessment.violations if v.rule_id == "RE_PAYLOAD_001")
        assert v.severity == RiskSeverity.CRITICAL

    def test_valid_payload_hits_financial_guard_not_payload_guard(self):
        """Valid required fields pass payload guard; missing equity hits RE_STATE_001."""
        orch = _make_orchestrator()
        payload = {"symbol": "BTC/USDT", "timeframe": "1h", "quantity": 0.5, "price": 50000.0}
        result = orch.process_execution_request(payload)
        assert result.assessment.decision == RiskDecision.BLOCK
        ids = [v.rule_id for v in result.assessment.violations]
        assert "RE_PAYLOAD_001" not in ids
        assert "RE_STATE_001" in ids


# ===========================================================================
# P1-C: risk_engine.evaluate_execution_request fails closed
# ===========================================================================

class TestPayloadValidationRiskEngine:

    def _mock_req(self, symbol="BTC/USDT", quantity=1.0, price=50000.0):
        m = MagicMock()
        m.symbol = symbol
        m.quantity = quantity
        m.price = price
        m.leverage = 1.0
        m.margin_required = 0.0
        m.timeframe = "1h"
        return m

    def test_missing_symbol_raises(self):
        engine = RiskEngine()
        req = self._mock_req(symbol=None)
        with pytest.raises(ValueError, match="RE_PAYLOAD_001"):
            engine.evaluate_execution_request(req)

    def test_zero_price_raises(self):
        engine = RiskEngine()
        req = self._mock_req(price=0.0)
        with pytest.raises(ValueError, match="RE_PAYLOAD_001"):
            engine.evaluate_execution_request(req)

    def test_none_price_no_kwarg_raises(self):
        engine = RiskEngine()
        req = self._mock_req(price=None)
        with pytest.raises(ValueError, match="RE_PAYLOAD_001"):
            engine.evaluate_execution_request(req)

    def test_zero_quantity_raises(self):
        engine = RiskEngine()
        req = self._mock_req(quantity=0.0)
        with pytest.raises(ValueError, match="RE_PAYLOAD_001"):
            engine.evaluate_execution_request(req)

    def test_negative_quantity_raises(self):
        engine = RiskEngine()
        req = self._mock_req(quantity=-5.0)
        with pytest.raises(ValueError, match="RE_PAYLOAD_001"):
            engine.evaluate_execution_request(req)


# ===========================================================================
# P1-D: Explicit REVIEW / BLOCK / ALLOW event dispatch
# ===========================================================================

class TestDecisionEventDispatch:
    """Each RiskDecision produces exactly its expected events."""

    def _make_orch_with_decision(self, decision: RiskDecision):
        from risk_engine.core.models import (
            RiskAssessment, RiskViolation, RiskState,
            DrawdownRisk, ExposureRisk, PortfolioRisk,
            CircuitBreakerState,
        )
        import unittest.mock as _mock
        import risk_engine.analysis.drawdown_engine as de_mod
        import risk_engine.analysis.exposure_engine as ee_mod
        import risk_engine.analysis.circuit_breakers as cb_mod
        import risk_engine.analysis.rules_engine as re_mod

        violations = (
            [RiskViolation(rule_id="RE_TEST_001", severity=RiskSeverity.HIGH, message="Review flag")]
            if decision == RiskDecision.REVIEW else []
        )
        assessment = RiskAssessment(
            overall_score=85.0 if decision == RiskDecision.ALLOW else 82.0,
            decision=decision,
            factors=[],
            violations=violations,
        )
        mock_rules = MagicMock()
        mock_rules.evaluate_request.return_value = RiskState(
            symbol="BTC/USDT", timeframe="1h", assessment=assessment,
        )

        mock_bus = MagicMock()
        orch = _make_orchestrator(event_bus=mock_bus)

        patchers = [
            _mock.patch.object(de_mod, "DrawdownEngine", return_value=MagicMock(
                calculate_drawdown=MagicMock(return_value=(DrawdownRisk(), "HEALTHY", False))
            )),
            _mock.patch.object(ee_mod, "ExposureEngine", return_value=MagicMock(
                calculate_exposures=MagicMock(return_value=(ExposureRisk(), PortfolioRisk()))
            )),
            _mock.patch.object(cb_mod, "CircuitBreakerEngine", return_value=MagicMock(
                evaluate_breakers=MagicMock(return_value=(CircuitBreakerState(halt_trading=False), []))
            )),
            _mock.patch.object(re_mod, "RiskRulesEngine", return_value=mock_rules),
        ]
        for p in patchers:
            p.start()

        return orch, mock_bus, patchers

    def _stop(self, patchers):
        for p in patchers:
            p.stop()

    def test_allow_publishes_execution_approved_only(self):
        orch, bus, p = self._make_orch_with_decision(RiskDecision.ALLOW)
        try:
            orch.process_execution_request(_valid_financial_payload())
            types = [type(c.args[0]).__name__ for c in bus.publish.call_args_list]
            assert "ExecutionApproved" in types
            assert "ExecutionRejected" not in types
            assert "RiskReview" not in types
        finally:
            self._stop(p)

    def test_block_publishes_execution_rejected_not_review(self):
        orch, bus, p = self._make_orch_with_decision(RiskDecision.BLOCK)
        try:
            orch.process_execution_request(_valid_financial_payload())
            types = [type(c.args[0]).__name__ for c in bus.publish.call_args_list]
            assert "ExecutionRejected" in types
            assert "ExecutionApproved" not in types
            assert "RiskReview" not in types
        finally:
            self._stop(p)

    def test_review_publishes_risk_review_not_execution_rejected(self):
        orch, bus, p = self._make_orch_with_decision(RiskDecision.REVIEW)
        try:
            orch.process_execution_request(_valid_financial_payload())
            types = [type(c.args[0]).__name__ for c in bus.publish.call_args_list]
            assert "RiskReview" in types, f"RiskReview missing. Published: {types}"
            assert "ExecutionRejected" not in types, "REVIEW must NOT emit ExecutionRejected"
            assert "ExecutionApproved" not in types, "REVIEW must NOT emit ExecutionApproved"
        finally:
            self._stop(p)
