"""Unit tests for the ConfidenceCalculator scoring algorithms."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
import pytest

from knowledge.confidence.calculator import ConfidenceCalculator
from knowledge.models import Evidence, SourceReference


def test_confidence_volume_scaling():
    """Verify that confidence increases with the number of evidence records."""
    ref = SourceReference(ref_type="backtest", ref_id="run-1", description="Test")
    
    e1 = Evidence(evidence_id="ev-1", source=ref, metric_name="sharpe", metric_value=1.5, sample_size=100)
    e2 = Evidence(evidence_id="ev-2", source=ref, metric_name="sharpe", metric_value=1.6, sample_size=100)
    
    # 0 evidence -> 0.0 confidence
    assert ConfidenceCalculator.calculate_confidence([]) == 0.0
    
    # 1 evidence
    conf_1 = ConfidenceCalculator.calculate_confidence([e1])
    # 2 evidence -> should be higher
    conf_2 = ConfidenceCalculator.calculate_confidence([e1, e2])
    
    assert conf_2 > conf_1
    assert 0.0 < conf_1 < 1.0


def test_confidence_quality_sample_sizing():
    """Verify that evidence with larger sample size yields higher confidence."""
    ref = SourceReference(ref_type="backtest", ref_id="run-1", description="Test")
    
    e_small = Evidence(evidence_id="ev-1", source=ref, metric_name="sharpe", metric_value=1.5, sample_size=5)
    e_large = Evidence(evidence_id="ev-2", source=ref, metric_name="sharpe", metric_value=1.5, sample_size=500)
    
    conf_small = ConfidenceCalculator.calculate_confidence([e_small])
    conf_large = ConfidenceCalculator.calculate_confidence([e_large])
    
    assert conf_large > conf_small


def test_confidence_recency_decay():
    """Verify that confidence decays over time for older evidence."""
    ref = SourceReference(ref_type="backtest", ref_id="run-1", description="Test")
    
    # Current evidence
    e_now = Evidence(evidence_id="ev-1", source=ref, metric_name="sharpe", metric_value=1.5, sample_size=100, created_at=datetime.now(timezone.utc))
    # 2 years old evidence
    two_years_ago = datetime.now(timezone.utc) - timedelta(days=730)
    e_old = Evidence(evidence_id="ev-2", source=ref, metric_name="sharpe", metric_value=1.5, sample_size=100, created_at=two_years_ago)
    
    conf_now = ConfidenceCalculator.calculate_confidence([e_now], decay_half_life_days=365.0)
    conf_old = ConfidenceCalculator.calculate_confidence([e_old], decay_half_life_days=365.0)
    
    assert conf_now > conf_old


def test_confidence_conflict_discount():
    """Verify that conflicts apply a 50% discount penalty to confidence score."""
    ref = SourceReference(ref_type="backtest", ref_id="run-1", description="Test")
    e = Evidence(evidence_id="ev-1", source=ref, metric_name="sharpe", metric_value=1.5, sample_size=100)
    
    conf_no_conflict = ConfidenceCalculator.calculate_confidence([e], has_conflict=False)
    conf_conflict = ConfidenceCalculator.calculate_confidence([e], has_conflict=True)
    
    assert pytest.approx(conf_conflict) == conf_no_conflict * 0.5
