"""Unit tests for the Risk Engine models."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from risk_engine.core.enums import RiskDecision, RiskSeverity
from risk_engine.core.models import (
    RiskFactor,
    RiskAssessment,
    RiskState,
    RiskSnapshot,
)


def test_risk_factor_validation():
    """Verify RiskFactor constraints and immutability."""
    factor = RiskFactor(
        id="RE_RULE_1",
        name="Test Risk",
        severity=RiskSeverity.HIGH,
        score=20.0,
        description="Test risk check details.",
    )
    assert factor.id == "RE_RULE_1"
    assert factor.name == "Test Risk"
    assert factor.severity == RiskSeverity.HIGH
    assert factor.score == 20.0

    # Immutability check
    with pytest.raises(ValidationError):
        factor.score = 30.0


def test_risk_assessment_validation():
    """Verify RiskAssessment structures and immutability."""
    factor = RiskFactor(
        id="RE_RULE_1",
        name="Test Risk",
        severity=RiskSeverity.HIGH,
        score=20.0,
        description="Test description",
    )
    assessment = RiskAssessment(
        overall_score=80.0,
        decision=RiskDecision.REVIEW,
        factors=[factor],
        violations=["Validation error message"],
    )

    assert assessment.overall_score == 80.0
    assert assessment.decision == RiskDecision.REVIEW
    assert assessment.factors == [factor]
    assert assessment.violations == ["Validation error message"]

    # Constraint check: score must be between 0 and 100
    with pytest.raises(ValidationError):
        RiskAssessment(overall_score=150.0, decision=RiskDecision.ALLOW)

    with pytest.raises(ValidationError):
        RiskAssessment(overall_score=-5.0, decision=RiskDecision.ALLOW)


def test_risk_state_validation():
    """Verify RiskState attributes and updated_at defaults."""
    dt = datetime.now(timezone.utc)
    assessment = RiskAssessment(
        overall_score=100.0,
        decision=RiskDecision.ALLOW,
    )
    state = RiskState(
        symbol="BTCUSDT",
        timeframe="1h",
        assessment=assessment,
        updated_at=dt,
    )

    assert state.symbol == "BTCUSDT"
    assert state.timeframe == "1h"
    assert state.assessment == assessment
    assert state.updated_at == dt

    # Immutability check
    with pytest.raises(ValidationError):
        state.symbol = "ETHUSDT"


def test_risk_snapshot_validation():
    """Verify RiskSnapshot mapping timeframe to RiskState."""
    dt = datetime.now(timezone.utc)
    assessment = RiskAssessment(
        overall_score=100.0,
        decision=RiskDecision.ALLOW,
    )
    state = RiskState(
        symbol="BTCUSDT",
        timeframe="1h",
        assessment=assessment,
        updated_at=dt,
    )

    snapshot = RiskSnapshot(
        snapshot_id="snap-123",
        symbol="BTCUSDT",
        timestamp=dt,
        states={"1h": state},
    )

    assert snapshot.snapshot_id == "snap-123"
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.timestamp == dt
    assert snapshot.states["1h"] == state
