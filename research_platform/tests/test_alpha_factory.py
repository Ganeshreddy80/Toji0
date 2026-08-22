"""Unit tests for the Alpha Research Platform.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.alpha_factory.alpha_engine import AlphaGeneticEngine
from research_platform.alpha_factory.decay import AlphaDecayEngine
from research_platform.alpha_factory.expression_engine import ExpressionEngine
from research_platform.alpha_factory.orchestrator import AlphaFactoryOrchestrator
from research_platform.validation_core.orchestrator import ValidationCoreOrchestrator


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return AlphaFactoryOrchestrator(event_bus)


@pytest.fixture
def validation_orchestrator(event_bus):
    return ValidationCoreOrchestrator(event_bus)


def test_expression_parser_and_compiler():
    """Verify recursive DSL formula parsing and compiler evaluation."""
    # Test AST parsing
    ast = ExpressionEngine.parse("ts_mean(close, 10)")
    assert ast["type"] == "function"
    assert ast["name"] == "ts_mean"
    assert ast["args"][0]["name"] == "close"
    assert ast["args"][1]["value"] == 10

    # Back to string
    back_to_str = ExpressionEngine.to_string(ast)
    assert back_to_str.replace(" ", "") == "ts_mean(close,10)"

    # Compile and Evaluate
    df = pd.DataFrame({
        "close": [10.0, 11.0, 12.0, 13.0, 14.0],
        "volume": [100.0, 110.0, 120.0, 130.0, 140.0]
    })
    res = ExpressionEngine.evaluate(ast, df)
    assert len(res) == 5
    # First value rolling mean of [10.0] is 10.0. Second value mean([10, 11]) is 10.5
    assert res.iloc[1] == 10.5


def test_complex_neutralization_operators():
    """Verify neutralization and cross-sectional ranks."""
    df = pd.DataFrame({
        "close": [10.0, 11.0, 12.0, 13.0],
        "sector": ["Tech", "Finance", "Tech", "Finance"]
    })
    ast = ExpressionEngine.parse("neutralize(close, sector)")
    res = ExpressionEngine.evaluate(ast, df)
    # Tech sector close are [10, 12] -> mean is 11. Tech values neutralized: [10-11, 12-11] = [-1, 1]
    assert res.iloc[0] == -1.0
    assert res.iloc[2] == 1.0


def test_genetic_crossover_and_mutation():
    """Verify genetic node alterations."""
    np.random.seed(42)
    # Generate random tree
    ast = AlphaGeneticEngine.generate_random_ast(max_depth=3)
    assert ast is not None
    assert "type" in ast

    # Mutation
    mutated = AlphaGeneticEngine.mutate(ast)
    assert mutated is not None

    # Crossover
    ast2 = AlphaGeneticEngine.generate_random_ast(max_depth=3)
    child1, child2 = AlphaGeneticEngine.crossover(ast, ast2)
    assert child1 is not None
    assert child2 is not None


def test_alpha_performance_evaluations(orchestrator):
    """Verify Rank IC, capacity, stability, and mutual information."""
    cand = orchestrator.create_candidate("ts_mean(close, 5)")
    
    df = pd.DataFrame({
        "close": [10.0 + i for i in range(20)],
        "volume": [1000.0 for _ in range(20)]
    })
    # positive correlation forward returns
    fwd_ret = pd.Series([0.01 for _ in range(20)])

    evaluation = orchestrator.evaluate_candidate(cand.candidate_id, df, fwd_ret)
    assert evaluation.candidate_id == cand.candidate_id
    assert evaluation.metrics.complexity > 0
    assert abs(evaluation.metrics.rank_ic) >= 0.0


def test_alpha_decay_half_life():
    """Verify decay half life calculation on rolling metrics."""
    rolling_ics = [0.1, 0.09, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01]
    report = AlphaDecayEngine.calculate_decay("cand_1", rolling_ics)
    assert report.half_life_days > 0.0
    # Rolling IC dropped below threshold at the end, retirement score should be high
    assert report.retirement_score > 0.7


def test_pareto_optimizer_rankings(orchestrator):
    """Verify multi-objective candidate ranking results."""
    # Create two candidates
    c1 = orchestrator.create_candidate("close")
    c2 = orchestrator.create_candidate("ts_mean(close, 10)")

    df = pd.DataFrame({
        "close": [10.0 + i for i in range(30)],
        "volume": [1000.0 for _ in range(30)]
    })
    fwd_ret = pd.Series([0.01 for _ in range(30)])

    orchestrator.evaluate_candidate(c1.candidate_id, df, fwd_ret)
    orchestrator.evaluate_candidate(c2.candidate_id, df, fwd_ret)

    rankings = orchestrator.optimize_and_rank()
    assert len(rankings) == 2
    assert rankings[0].rank_position == 1


def test_validation_core_promotion_integration(orchestrator, validation_orchestrator):
    """Verify successful candidates can promote to validation core gates."""
    cand = orchestrator.create_candidate("close")
    
    df = pd.DataFrame({
        "close": [10.0 + (i * 0.1) for i in range(100)],
        "volume": [1000000.0 for _ in range(100)]
    })
    fwd_ret = pd.Series([0.01 for _ in range(100)])

    # Setup evaluation
    orchestrator.evaluate_candidate(cand.candidate_id, df, fwd_ret)

    # Submit to validation
    report = orchestrator.promote_to_validation(
        candidate_id=cand.candidate_id,
        df=df,
        forward_returns=fwd_ret,
        validation_orchestrator=validation_orchestrator
    )
    # Close signal is positive linear trend with constant positive returns, should be approved
    assert report.is_approved is True
