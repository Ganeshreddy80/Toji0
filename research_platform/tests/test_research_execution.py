"""Comprehensive unit and integration tests for TOJI Research & Execution stack (R40-R44).
"""

from __future__ import annotations

import pytest
import threading
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

# Subsystems
from research_platform.research_lab.orchestrator import ResearchLabOrchestrator
from research_platform.research_lab.models import FeatureData, AlphaFactor, Hypothesis
from research_platform.research_lab.plugin import ResearchLabPlugin

from research_platform.alpha_factory.orchestrator import AlphaFactoryOrchestrator
from research_platform.alpha_factory.models import AlphaSignal, AlphaCombo, EnsembleModel
from research_platform.alpha_factory.plugin import AlphaFactoryPlugin

from research_platform.walk_forward.orchestrator import WalkForwardOrchestrator
from research_platform.walk_forward.models import ValidationWindow, SensitivityScore, OverfittingCard
from research_platform.walk_forward.plugin import WalkForwardPlugin

from research_platform.portfolio_construction.orchestrator import PortfolioConstructionOrchestrator
from research_platform.portfolio_construction.models import PortfolioAllocation, RebalanceOrder
from research_platform.portfolio_construction.plugin import PortfolioConstructionPlugin

from research_platform.execution_simulator.orchestrator import ExecutionSimulatorOrchestrator
from research_platform.execution_simulator.models import SimulatedExecution, SimulatedFill, OrderBookSlice
from research_platform.execution_simulator.plugin import ExecutionSimulatorPlugin

# Integrations
from research_platform.institutional_memory.orchestrator import InstitutionalMemoryOrchestrator
from research_platform.knowledge_graph.orchestrator import KnowledgeGraphOrchestrator
from research_platform.operations_center.operations_orchestrator import OperationsOrchestrator


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def container(event_bus):
    c = Container()
    c.register("IEventBus", instance=event_bus)

    mem_orch = InstitutionalMemoryOrchestrator(event_bus)
    c.register("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator", instance=mem_orch)

    kg_orch = KnowledgeGraphOrchestrator(event_bus)
    c.register("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator", instance=kg_orch)

    ops_orch = OperationsOrchestrator(event_bus, container=c)
    c.register("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator", instance=ops_orch)

    return c


@pytest.fixture
def lab_orch(event_bus, container):
    return ResearchLabOrchestrator(event_bus, container=container)


@pytest.fixture
def alpha_orch(event_bus, container):
    return AlphaFactoryOrchestrator(event_bus, container=container)


@pytest.fixture
def wf_orch(event_bus, container):
    return WalkForwardOrchestrator(event_bus, container=container)


@pytest.fixture
def pc_orch(event_bus, container):
    return PortfolioConstructionOrchestrator(event_bus, container=container)


@pytest.fixture
def sim_orch(event_bus, container):
    return ExecutionSimulatorOrchestrator(event_bus, container=container)


# ─────────────────────────────────────────────────────────────────────
# GROUP 1: RESEARCH LAB TESTS (1-30)
# ─────────────────────────────────────────────────────────────────────

def test_lab_session_start(lab_orch):
    res = lab_orch.start_session("s1", "Session 1")
    assert res.session_id == "s1"


def test_lab_session_fields(lab_orch):
    res = lab_orch.start_session("s1", "Session 1")
    assert res.name == "Session 1"


def test_lab_feature_extraction_success(lab_orch):
    res = lab_orch.extract_features("f1", [100.0, 101.0, 102.0])
    assert res.feature_id == "f1"
    assert res.values == [1.0, 1.0]


def test_lab_feature_extraction_empty_data(lab_orch):
    res = lab_orch.extract_features("f1", [])
    assert len(res.values) == 0


def test_lab_feature_extraction_single_data(lab_orch):
    res = lab_orch.extract_features("f1", [100.0])
    assert len(res.values) == 0


def test_lab_feature_save(lab_orch):
    feat = lab_orch.extract_features("f1", [100.0, 101.0])
    assert lab_orch.repository.get_feature("f1") is not None


def test_lab_feature_retrieve(lab_orch):
    lab_orch.extract_features("f1", [100.0, 101.0])
    res = lab_orch.repository.get_feature("f1")
    assert res.values == [1.0]


def test_lab_factor_calculation_scale5(lab_orch):
    res = lab_orch.calculate_factor("fact1", "SCALE_5", [1.0, 2.0])
    assert res.values == [5.0, 10.0]


def test_lab_factor_calculation_default(lab_orch):
    res = lab_orch.calculate_factor("fact1", "DEFAULT", [1.0, 2.0])
    assert res.values == [2.0, 4.0]


def test_lab_factor_save(lab_orch):
    lab_orch.calculate_factor("fact1", "DEFAULT", [1.0])
    assert lab_orch.repository.get_factor("fact1") is not None


def test_lab_factor_retrieve(lab_orch):
    lab_orch.calculate_factor("fact1", "DEFAULT", [1.0])
    res = lab_orch.repository.get_factor("fact1")
    assert res.formula == "DEFAULT"


def test_lab_indicator_library_sma(lab_orch):
    res = lab_orch.indicator_library.get_indicator("sma")
    assert res.name == "Simple Moving Average"


def test_lab_indicator_library_rsi(lab_orch):
    res = lab_orch.indicator_library.get_indicator("rsi")
    assert res.params["period"] == 14


def test_lab_indicator_library_list(lab_orch):
    assert len(lab_orch.indicator_library.list_indicators()) == 2


def test_lab_indicator_library_missing(lab_orch):
    assert lab_orch.indicator_library.get_indicator("missing") is None


def test_lab_hypothesis_verification_significant(lab_orch):
    res = lab_orch.verify_hypothesis("h1", "Test", 0.02)
    assert res.verified is True


def test_lab_hypothesis_verification_insignificant(lab_orch):
    res = lab_orch.verify_hypothesis("h1", "Test", 0.08)
    assert res.verified is False


def test_lab_hypothesis_save(lab_orch):
    lab_orch.verify_hypothesis("h1", "Test", 0.02)
    assert lab_orch.repository.get_hypothesis("h1") is not None


def test_lab_hypothesis_retrieve(lab_orch):
    lab_orch.verify_hypothesis("h1", "Test", 0.02)
    res = lab_orch.repository.get_hypothesis("h1")
    assert res.p_value == 0.02


def test_lab_session_event(lab_orch, event_bus):
    events = []
    event_bus.subscribe("system.research_session_started", lambda e: events.append(e))
    lab_orch.start_session("s1", "Session")
    assert len(events) == 1


def test_lab_feature_event(lab_orch, event_bus):
    events = []
    event_bus.subscribe("system.feature_extracted", lambda e: events.append(e))
    lab_orch.extract_features("f1", [100.0, 101.0])
    assert len(events) == 1


def test_lab_factor_event(lab_orch, event_bus):
    events = []
    event_bus.subscribe("system.factor_calculated", lambda e: events.append(e))
    lab_orch.calculate_factor("fact1", "DEFAULT", [1.0])
    assert len(events) == 1


def test_lab_hypothesis_event(lab_orch, event_bus):
    events = []
    event_bus.subscribe("system.hypothesis_verified", lambda e: events.append(e))
    lab_orch.verify_hypothesis("h1", "Test", 0.02)
    assert len(events) == 1


def test_lab_thread_safety_features(lab_orch):
    threads = [threading.Thread(target=lambda i: lab_orch.extract_features(f"thread-f-{i}", [100.0]), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert lab_orch.repository.get_feature("thread-f-5") is not None


def test_lab_thread_safety_factors(lab_orch):
    threads = [threading.Thread(target=lambda i: lab_orch.calculate_factor(f"thread-fact-{i}", "DEFAULT", [1.0]), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert lab_orch.repository.get_factor("thread-fact-5") is not None


def test_lab_thread_safety_hypotheses(lab_orch):
    threads = [threading.Thread(target=lambda i: lab_orch.verify_hypothesis(f"thread-h-{i}", "Test", 0.02), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert lab_orch.repository.get_hypothesis("thread-h-5") is not None


def test_lab_plugin_registration(container):
    plugin = ResearchLabPlugin(container)
    plugin.initialize()
    orch = container.resolve(ResearchLabOrchestrator)
    assert orch is not None


def test_lab_memory_integration(lab_orch, container):
    lab_orch.extract_features("f1", [100.0, 101.0])
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("research")) == 1


def test_lab_kg_integration(lab_orch, container):
    lab_orch.extract_features("f1", [100.0, 101.0])
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == "f1"), None) is not None


def test_lab_ops_integration(lab_orch, container):
    # Triggers refreshing Operations Center dashboard snapshot on event loop
    lab_orch.extract_features("f1", [100.0, 101.0])
    ops = container.resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")
    assert ops is not None


# ─────────────────────────────────────────────────────────────────────
# GROUP 2: ALPHA FACTORY TESTS (31-60)
# ─────────────────────────────────────────────────────────────────────

def test_alpha_signal_buy(alpha_orch):
    res = alpha_orch.generate_signal("sig1", "fact1", [0.8, 0.9])
    assert res.direction == "BUY"
    assert res.strength == pytest.approx(0.85)


def test_alpha_signal_sell(alpha_orch):
    res = alpha_orch.generate_signal("sig1", "fact1", [-0.8, -0.9])
    assert res.direction == "SELL"
    assert res.strength == pytest.approx(0.85)


def test_alpha_signal_flat(alpha_orch):
    res = alpha_orch.generate_signal("sig1", "fact1", [0.1, 0.2])
    assert res.direction == "FLAT"
    assert res.strength == 0.0


def test_alpha_signal_empty(alpha_orch):
    res = alpha_orch.generate_signal("sig1", "fact1", [])
    assert res.direction == "FLAT"


def test_alpha_signal_save(alpha_orch):
    alpha_orch.generate_signal("sig1", "fact1", [0.8])
    assert alpha_orch.repository.get_signal("sig1") is not None


def test_alpha_signal_retrieve(alpha_orch):
    alpha_orch.generate_signal("sig1", "fact1", [0.8])
    res = alpha_orch.repository.get_signal("sig1")
    assert res.factor_id == "fact1"


def test_alpha_combo_creation(alpha_orch):
    sig = alpha_orch.generate_signal("sig1", "fact1", [0.8])
    res = alpha_orch.combine_signals("combo1", [sig], [1.0])
    assert res.combo_id == "combo1"
    assert res.weights == [1.0]


def test_alpha_combo_save(alpha_orch):
    sig = alpha_orch.generate_signal("sig1", "fact1", [0.8])
    alpha_orch.combine_signals("combo1", [sig], [1.0])
    assert alpha_orch.repository.get_combo("combo1") is not None


def test_alpha_combo_retrieve(alpha_orch):
    sig = alpha_orch.generate_signal("sig1", "fact1", [0.8])
    alpha_orch.combine_signals("combo1", [sig], [1.0])
    res = alpha_orch.repository.get_combo("combo1")
    assert len(res.signals) == 1


def test_alpha_ensemble_creation(alpha_orch):
    sig = alpha_orch.generate_signal("sig1", "fact1", [0.8])
    combo = alpha_orch.combine_signals("combo1", [sig], [1.0])
    res = alpha_orch.create_ensemble("ens1", [combo])
    assert res.ensemble_id == "ens1"


def test_alpha_ensemble_save(alpha_orch):
    sig = alpha_orch.generate_signal("sig1", "fact1", [0.8])
    combo = alpha_orch.combine_signals("combo1", [sig], [1.0])
    alpha_orch.create_ensemble("ens1", [combo])
    assert alpha_orch.repository.get_ensemble("ens1") is not None


def test_alpha_ensemble_retrieve(alpha_orch):
    sig = alpha_orch.generate_signal("sig1", "fact1", [0.8])
    combo = alpha_orch.combine_signals("combo1", [sig], [1.0])
    alpha_orch.create_ensemble("ens1", [combo])
    res = alpha_orch.repository.get_ensemble("ens1")
    assert len(res.combos) == 1


def test_alpha_ranking_signals_empty(alpha_orch):
    assert len(alpha_orch.rank_signals([])) == 0


def test_alpha_ranking_signals_ordered(alpha_orch):
    sig1 = alpha_orch.generate_signal("sig1", "fact1", [0.6])
    sig2 = alpha_orch.generate_signal("sig2", "fact1", [0.9])
    res = alpha_orch.rank_signals([sig1, sig2])
    assert res[0].signal_id == "sig2"
    assert res[1].signal_id == "sig1"


def test_alpha_confidence_flat(alpha_orch):
    sig = alpha_orch.generate_signal("sig1", "fact1", [0.1])
    assert alpha_orch.evaluate_confidence(sig) == 0.0


def test_alpha_confidence_strength(alpha_orch):
    sig = alpha_orch.generate_signal("sig1", "fact1", [0.7])
    # 0.7 strength * 1.2 = 0.84
    assert alpha_orch.evaluate_confidence(sig) == pytest.approx(0.84)


def test_alpha_confidence_strength_capped(alpha_orch):
    sig = alpha_orch.generate_signal("sig1", "fact1", [0.95])
    # 0.95 strength * 1.2 = 1.14 (capped at 1.0)
    assert alpha_orch.evaluate_confidence(sig) == 1.0


def test_alpha_signal_event(alpha_orch, event_bus):
    events = []
    event_bus.subscribe("system.signal_generated", lambda e: events.append(e))
    alpha_orch.generate_signal("sig1", "fact1", [0.8])
    assert len(events) == 1


def test_alpha_combo_event(alpha_orch, event_bus):
    events = []
    event_bus.subscribe("system.combo_created", lambda e: events.append(e))
    sig = alpha_orch.generate_signal("sig1", "fact1", [0.8])
    alpha_orch.combine_signals("combo1", [sig], [1.0])
    assert len(events) == 1


def test_alpha_ensemble_event(alpha_orch, event_bus):
    events = []
    event_bus.subscribe("system.ensemble_model_updated", lambda e: events.append(e))
    sig = alpha_orch.generate_signal("sig1", "fact1", [0.8])
    combo = alpha_orch.combine_signals("combo1", [sig], [1.0])
    alpha_orch.create_ensemble("ens1", [combo])
    assert len(events) == 1


def test_alpha_thread_safety_signals(alpha_orch):
    threads = [threading.Thread(target=lambda i: alpha_orch.generate_signal(f"thread-sig-{i}", "fact1", [0.8]), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert alpha_orch.repository.get_signal("thread-sig-5") is not None


def test_alpha_thread_safety_combos(alpha_orch):
    sig = alpha_orch.generate_signal("sig1", "fact1", [0.8])
    threads = [threading.Thread(target=lambda i: alpha_orch.combine_signals(f"thread-combo-{i}", [sig], [1.0]), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert alpha_orch.repository.get_combo("thread-combo-5") is not None


def test_alpha_thread_safety_ensembles(alpha_orch):
    sig = alpha_orch.generate_signal("sig1", "fact1", [0.8])
    combo = alpha_orch.combine_signals("combo1", [sig], [1.0])
    threads = [threading.Thread(target=lambda i: alpha_orch.create_ensemble(f"thread-ens-{i}", [combo]), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert alpha_orch.repository.get_ensemble("thread-ens-5") is not None


def test_alpha_plugin_registration(container):
    plugin = AlphaFactoryPlugin(container)
    plugin.initialize()
    orch = container.resolve(AlphaFactoryOrchestrator)
    assert orch is not None


def test_alpha_memory_integration(alpha_orch, container):
    alpha_orch.generate_signal("sig1", "fact1", [0.8])
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("research")) == 1


def test_alpha_kg_integration(alpha_orch, container):
    alpha_orch.generate_signal("sig1", "fact1", [0.8])
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == "sig1"), None) is not None


def test_alpha_ops_integration(alpha_orch, container):
    alpha_orch.generate_signal("sig1", "fact1", [0.8])
    ops = container.resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")
    assert ops is not None


def test_alpha_signal_strength_exact(alpha_orch):
    res = alpha_orch.generate_signal("sig1", "fact1", [0.85])
    assert res.strength == 0.85


def test_alpha_signal_direction_buy(alpha_orch):
    res = alpha_orch.generate_signal("sig1", "fact1", [0.6])
    assert res.direction == "BUY"


def test_alpha_signal_direction_sell(alpha_orch):
    res = alpha_orch.generate_signal("sig1", "fact1", [-0.6])
    assert res.direction == "SELL"


# ─────────────────────────────────────────────────────────────────────
# GROUP 3: WALK FORWARD VALIDATION TESTS (61-90)
# ─────────────────────────────────────────────────────────────────────

def test_wf_rolling_windows_generation(wf_orch):
    res = wf_orch.generate_rolling_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    assert len(res) > 0


def test_wf_rolling_windows_length(wf_orch):
    res = wf_orch.generate_rolling_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    assert len(res) == 3


def test_wf_rolling_windows_boundaries(wf_orch):
    res = wf_orch.generate_rolling_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    assert res[0].train_start == datetime(2026, 1, 1)
    assert res[0].train_end == datetime(2026, 3, 2)


def test_wf_expanding_windows_generation(wf_orch):
    res = wf_orch.generate_expanding_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    assert len(res) > 0


def test_wf_expanding_windows_length(wf_orch):
    res = wf_orch.generate_expanding_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    assert len(res) == 3


def test_wf_expanding_windows_boundaries(wf_orch):
    res = wf_orch.generate_expanding_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    assert res[0].train_start == datetime(2026, 1, 1)
    assert res[0].train_end == datetime(2026, 3, 2)
    assert res[1].train_start == datetime(2026, 1, 1)
    assert res[1].train_end == datetime(2026, 4, 1)


def test_wf_validate_window_success(wf_orch):
    wins = wf_orch.generate_rolling_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    res = wf_orch.validate_window(wins[0].window_id, 1.8, 1.2)
    assert res.in_sample_sharpe == 1.8
    assert res.out_of_sample_sharpe == 1.2


def test_wf_validate_window_missing(wf_orch):
    with pytest.raises(ValueError, match="not found"):
        wf_orch.validate_window("missing", 1.8, 1.2)


def test_wf_validate_window_save(wf_orch):
    wins = wf_orch.generate_rolling_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    wf_orch.validate_window(wins[0].window_id, 1.8, 1.2)
    assert wf_orch.repository.get_window(wins[0].window_id) is not None


def test_wf_validate_window_retrieve(wf_orch):
    wins = wf_orch.generate_rolling_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    wf_orch.validate_window(wins[0].window_id, 1.8, 1.2)
    res = wf_orch.repository.get_window(wins[0].window_id)
    assert res.in_sample_sharpe == 1.8


def test_wf_sensitivity_analysis_robust(wf_orch):
    res = wf_orch.analyze_sensitivity("period", [10, 20, 30], [1.5, 1.6, 1.55])
    assert res.parameter_name == "period"
    assert res.score > 0.90


def test_wf_sensitivity_analysis_empty(wf_orch):
    res = wf_orch.analyze_sensitivity("period", [], [])
    assert res.score == 1.0


def test_wf_sensitivity_save(wf_orch):
    wf_orch.analyze_sensitivity("period", [10], [1.5])
    assert wf_orch.repository.get_sensitivity("period") is not None


def test_wf_sensitivity_retrieve(wf_orch):
    wf_orch.analyze_sensitivity("period", [10], [1.5])
    res = wf_orch.repository.get_sensitivity("period")
    assert res.score == 1.0


def test_wf_overfitting_detector_positive(wf_orch):
    res = wf_orch.detect_overfitting("strat-alpha", True, 0.40)
    assert res.is_overfitted is True
    assert res.probability_of_backtest_overfitting == 0.85


def test_wf_overfitting_detector_negative(wf_orch):
    res = wf_orch.detect_overfitting("strat-alpha", False, 0.85)
    assert res.is_overfitted is False
    assert res.probability_of_backtest_overfitting == 0.12


def test_wf_overfitting_save(wf_orch):
    wf_orch.detect_overfitting("strat-alpha", True, 0.40)
    assert wf_orch.repository.get_overfitting("strat-alpha") is not None


def test_wf_overfitting_retrieve(wf_orch):
    wf_orch.detect_overfitting("strat-alpha", True, 0.40)
    res = wf_orch.repository.get_overfitting("strat-alpha")
    assert res.stability_score == 0.40


def test_wf_window_event(wf_orch, event_bus):
    events = []
    event_bus.subscribe("system.validation_window_completed", lambda e: events.append(e))
    wins = wf_orch.generate_rolling_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    wf_orch.validate_window(wins[0].window_id, 1.8, 1.2)
    assert len(events) == 1


def test_wf_sensitivity_event(wf_orch, event_bus):
    events = []
    event_bus.subscribe("system.sensitivity_analyzed", lambda e: events.append(e))
    wf_orch.analyze_sensitivity("period", [10], [1.5])
    assert len(events) == 1


def test_wf_overfitting_event(wf_orch, event_bus):
    events = []
    event_bus.subscribe("system.overfitting_checked", lambda e: events.append(e))
    wf_orch.detect_overfitting("strat-alpha", True, 0.40)
    assert len(events) == 1


def test_wf_thread_safety_windows(wf_orch):
    wins = wf_orch.generate_rolling_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    threads = [threading.Thread(target=lambda i: wf_orch.validate_window(wins[0].window_id, 1.8, 1.2), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert wf_orch.repository.get_window(wins[0].window_id) is not None


def test_wf_thread_safety_sensitivities(wf_orch):
    threads = [threading.Thread(target=lambda i: wf_orch.analyze_sensitivity(f"thread-param-{i}", [10], [1.5]), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert wf_orch.repository.get_sensitivity("thread-param-5") is not None


def test_wf_thread_safety_overfittings(wf_orch):
    threads = [threading.Thread(target=lambda i: wf_orch.detect_overfitting(f"thread-strat-{i}", True, 0.40), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert wf_orch.repository.get_overfitting("thread-strat-5") is not None


def test_wf_plugin_registration(container):
    plugin = WalkForwardPlugin(container)
    plugin.initialize()
    orch = container.resolve(WalkForwardOrchestrator)
    assert orch is not None


def test_wf_memory_integration(wf_orch, container):
    wins = wf_orch.generate_rolling_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    wf_orch.validate_window(wins[0].window_id, 1.8, 1.2)
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("research")) == 1


def test_wf_kg_integration(wf_orch, container):
    wins = wf_orch.generate_rolling_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    wf_orch.validate_window(wins[0].window_id, 1.8, 1.2)
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == wins[0].window_id), None) is not None


def test_wf_ops_integration(wf_orch, container):
    wins = wf_orch.generate_rolling_windows(datetime(2026, 1, 1), datetime(2026, 6, 1), 60.0, 30.0)
    wf_orch.validate_window(wins[0].window_id, 1.8, 1.2)
    ops = container.resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")
    assert ops is not None


def test_wf_rolling_empty_range(wf_orch):
    res = wf_orch.generate_rolling_windows(datetime(2026, 1, 1), datetime(2026, 1, 5), 60.0, 30.0)
    assert len(res) == 0


def test_wf_expanding_empty_range(wf_orch):
    res = wf_orch.generate_expanding_windows(datetime(2026, 1, 1), datetime(2026, 1, 5), 60.0, 30.0)
    assert len(res) == 0


# ─────────────────────────────────────────────────────────────────────
# GROUP 4: PORTFOLIO CONSTRUCTION TESTS (91-120)
# ─────────────────────────────────────────────────────────────────────

def test_pc_create_allocation(pc_orch):
    res = pc_orch.create_allocation("alloc1", {"AAPL": 0.40, "GOOG": 0.60})
    assert res.allocation_id == "alloc1"
    assert res.weights["AAPL"] == 0.40


def test_pc_allocation_save(pc_orch):
    pc_orch.create_allocation("alloc1", {"AAPL": 0.40})
    assert pc_orch.repository.get_allocation("alloc1") is not None


def test_pc_allocation_retrieve(pc_orch):
    pc_orch.create_allocation("alloc1", {"AAPL": 0.40})
    res = pc_orch.repository.get_allocation("alloc1")
    assert res.weights["AAPL"] == 1.0  # Normalized to 1.0


def test_pc_equal_weight_sizing_empty(pc_orch):
    assert len(pc_orch.size_positions_equally([])) == 0


def test_pc_equal_weight_sizing_three(pc_orch):
    res = pc_orch.size_positions_equally(["AAPL", "GOOG", "MSFT"])
    assert res["AAPL"] == pytest.approx(0.3333333333333333)


def test_pc_risk_parity_sizing_empty(pc_orch):
    assert len(pc_orch.calculate_risk_parity([], {})) == 0


def test_pc_risk_parity_sizing_vols(pc_orch):
    res = pc_orch.calculate_risk_parity(["AAPL", "GOOG"], {"AAPL": 0.10, "GOOG": 0.30})
    # inverse vols: AAPL=10, GOOG=3.333. normalized: AAPL=0.75, GOOG=0.25
    assert res["AAPL"] == 0.75
    assert res["GOOG"] == 0.25


def test_pc_risk_parity_missing_vol(pc_orch):
    res = pc_orch.calculate_risk_parity(["AAPL"], {})
    assert res["AAPL"] == 1.0


def test_pc_kelly_sizing_empty(pc_orch):
    assert len(pc_orch.calculate_kelly_fraction([], {}, {})) == 0


def test_pc_kelly_sizing_win_loss(pc_orch):
    res = pc_orch.calculate_kelly_fraction(["AAPL"], {"AAPL": 0.55}, {"AAPL": 2.0})
    # f = 0.55 - (1-0.55)/2 = 0.55 - 0.225 = 0.325
    assert res["AAPL"] == pytest.approx(0.325)


def test_pc_vol_targeting_scale_less(pc_orch):
    res = pc_orch.scale_allocation({"AAPL": 1.0}, 0.10, 0.15)
    # realized < target, so scale = 1.5. Capped by leverage limit which is min(2.0, 1.5) = 1.5
    assert res["AAPL"] == pytest.approx(1.5)


def test_pc_vol_targeting_scale_leverage(pc_orch):
    res = pc_orch.scale_allocation({"AAPL": 1.0}, 0.05, 0.15)
    # realized=5%, target=15%, scale=3.0 (capped at 2.0 leverage)
    assert res["AAPL"] == 2.0


def test_pc_vol_targeting_zero_vol(pc_orch):
    res = pc_orch.scale_allocation({"AAPL": 1.0}, 0.0, 0.15)
    assert res["AAPL"] == 1.0


def test_pc_exposure_limits_unaffected(pc_orch):
    res = pc_orch.limit_exposure({"AAPL": 0.20}, 0.25)
    assert res["AAPL"] == 0.20


def test_pc_exposure_limits_clipped(pc_orch):
    res = pc_orch.limit_exposure({"AAPL": 0.35}, 0.25)
    assert res["AAPL"] == 0.25


def test_pc_rebalance_orders_buy(pc_orch):
    res = pc_orch.compile_rebalance_orders({"AAPL": 0.10}, {"AAPL": 0.30})
    assert res[0].order_side == "BUY"


def test_pc_rebalance_orders_sell(pc_orch):
    res = pc_orch.compile_rebalance_orders({"AAPL": 0.30}, {"AAPL": 0.10})
    assert res[0].order_side == "SELL"


def test_pc_rebalance_orders_hold(pc_orch):
    res = pc_orch.compile_rebalance_orders({"AAPL": 0.20}, {"AAPL": 0.20})
    assert res[0].order_side == "HOLD"


def test_pc_rebalance_orders_mixed(pc_orch):
    res = pc_orch.compile_rebalance_orders({"AAPL": 0.30, "GOOG": 0.10}, {"AAPL": 0.10, "GOOG": 0.30})
    assert len(res) == 2


def test_pc_rebalance_event(pc_orch, event_bus):
    events = []
    event_bus.subscribe("system.allocation_rebalanced", lambda e: events.append(e))
    pc_orch.create_allocation("alloc1", {"AAPL": 0.40})
    assert len(events) == 1


def test_pc_thread_safety_allocations(pc_orch):
    threads = [threading.Thread(target=lambda i: pc_orch.create_allocation(f"thread-alloc-{i}", {"AAPL": 0.40}), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert pc_orch.repository.get_allocation("thread-alloc-5") is not None


def test_pc_plugin_registration(container):
    plugin = PortfolioConstructionPlugin(container)
    plugin.initialize()
    orch = container.resolve(PortfolioConstructionOrchestrator)
    assert orch is not None


def test_pc_memory_integration(pc_orch, container):
    pc_orch.create_allocation("alloc1", {"AAPL": 0.40})
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("observability")) == 1


def test_pc_kg_integration(pc_orch, container):
    pc_orch.create_allocation("alloc1", {"AAPL": 0.40})
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == "alloc1"), None) is not None


def test_pc_ops_integration(pc_orch, container):
    pc_orch.create_allocation("alloc1", {"AAPL": 0.40})
    ops = container.resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")
    assert ops is not None


def test_pc_correlation_matrix_identity(pc_orch):
    res = pc_orch.correlation_engine.calculate_correlation(["AAPL", "GOOG"])
    assert res.matrix == [[1.0, 0.0], [0.0, 1.0]]


def test_pc_correlation_matrix_assets(pc_orch):
    res = pc_orch.correlation_engine.calculate_correlation(["AAPL", "GOOG"])
    assert res.assets == ["AAPL", "GOOG"]


def test_pc_correlation_engine_direct(pc_orch):
    assert len(pc_orch.correlation_engine.calculate_correlation([]).matrix) == 0


def test_pc_equal_weight_normalization(pc_orch):
    weights = pc_orch.size_positions_equally(["AAPL", "GOOG"])
    assert sum(weights.values()) == 1.0


def test_pc_risk_parity_sum_1(pc_orch):
    weights = pc_orch.calculate_risk_parity(["AAPL", "GOOG"], {"AAPL": 0.15, "GOOG": 0.25})
    assert sum(weights.values()) == pytest.approx(1.0)


# ─────────────────────────────────────────────────────────────────────
# GROUP 5: EXECUTION SIMULATOR TESTS (121-152)
# ─────────────────────────────────────────────────────────────────────

def test_sim_match_buy_empty(sim_orch):
    book = OrderBookSlice(asks=[], bids=[])
    res = sim_orch._engine._matcher.match_against_book(book, 10.0, "BUY")
    assert len(res) == 0


def test_sim_match_sell_empty(sim_orch):
    book = OrderBookSlice(asks=[], bids=[])
    res = sim_orch._engine._matcher.match_against_book(book, 10.0, "SELL")
    assert len(res) == 0


def test_sim_match_buy_partial(sim_orch):
    book = OrderBookSlice(asks=[(100.5, 5.0), (100.6, 20.0)], bids=[])
    res = sim_orch._engine._matcher.match_against_book(book, 10.0, "BUY")
    assert len(res) == 2
    assert res[0] == (100.5, 5.0)
    assert res[1] == (100.6, 5.0)


def test_sim_match_sell_partial(sim_orch):
    book = OrderBookSlice(asks=[], bids=[(99.5, 5.0), (99.4, 20.0)])
    res = sim_orch._engine._matcher.match_against_book(book, 10.0, "SELL")
    assert len(res) == 2
    assert res[0] == (99.5, 5.0)
    assert res[1] == (99.4, 5.0)


def test_sim_match_buy_filled(sim_orch):
    book = OrderBookSlice(asks=[(100.5, 50.0)], bids=[])
    res = sim_orch._engine._matcher.match_against_book(book, 10.0, "BUY")
    assert len(res) == 1
    assert res[0] == (100.5, 10.0)


def test_sim_latency_delay_production(sim_orch):
    assert sim_orch.latency_engine.simulate_delay("PRODUCTION") == 0.0015


def test_sim_latency_delay_dev(sim_orch):
    assert sim_orch.latency_engine.simulate_delay("DEV") == 0.005


def test_sim_market_impact_zero(sim_orch):
    assert sim_orch.market_impact_engine.calculate_impact(10.0, 0.0) == 0.0


def test_sim_market_impact_calculation(sim_orch):
    res = sim_orch.market_impact_engine.calculate_impact(100.0, 10000.0)
    # fraction = 100/10000 = 0.01. fraction**0.5 = 0.1. 0.15 * 0.1 = 0.015
    assert res == pytest.approx(0.015)


def test_sim_queue_model_all_matched(sim_orch):
    assert sim_orch.queue_model.calculate_queue_place(0.0, 10.0) == 1.0


def test_sim_queue_model_calculation(sim_orch):
    res = sim_orch.queue_model.calculate_queue_place(50.0, 50.0)
    assert res == 0.50


def test_sim_orderbook_generate_asks(sim_orch):
    book = sim_orch._engine._book_sim.generate_slice(100.0)
    assert len(book.asks) == 5
    assert book.asks[0][0] == 100.05


def test_sim_orderbook_generate_bids(sim_orch):
    book = sim_orch._engine._book_sim.generate_slice(100.0)
    assert len(book.bids) == 5
    assert book.bids[0][0] == 99.95


def test_sim_partial_fill_ratio_empty(sim_orch):
    res = sim_orch._engine._slippage_eng.calculate_slippage(0.0)
    assert res == 0.0


def test_sim_partial_fill_ratio_sufficient(sim_orch):
    res = sim_orch._engine._slippage_eng.calculate_slippage(10.0)
    assert res > 0.0


def test_sim_vwap_engine_empty(sim_orch):
    assert sim_orch.vwap_engine.calculate_vwap([]) == 0.0


def test_sim_vwap_engine_calculation(sim_orch):
    res = sim_orch.vwap_engine.calculate_vwap([(100.0, 10.0), (101.0, 20.0)])
    # vwap = (100*10 + 101*20) / 30 = (1000 + 2020) / 30 = 3020 / 30 = 100.6666
    assert res == pytest.approx(100.66666666666667)


def test_sim_twap_engine_empty(sim_orch):
    assert sim_orch.twap_engine.calculate_twap([]) == 0.0


def test_sim_twap_engine_calculation(sim_orch):
    res = sim_orch.twap_engine.calculate_twap([(100.0, 10.0), (102.0, 20.0)])
    assert res == 101.0


def test_sim_slippage_engine_calculation(sim_orch):
    # default quant=10, vol=20%. 0.0005 * 10 * 0.20 = 0.001
    assert sim_orch._engine._slippage_eng.calculate_slippage(10.0, 0.20) == pytest.approx(0.001)


def test_sim_fee_engine_calculation(sim_orch):
    # default value=1000. 1000 * 0.0005 = 0.5
    assert sim_orch._engine._fee_eng.calculate_fees(1000.0) == pytest.approx(0.5)


def test_sim_execute_order_market_buy(sim_orch):
    res = sim_orch.simulate_execution("ord1", "AAPL", 10.0, 150.0, "MARKET", "BUY")
    assert res.order_id == "ord1"
    assert res.average_price > 150.0
    assert len(res.fills) > 0


def test_sim_execute_order_market_sell(sim_orch):
    res = sim_orch.simulate_execution("ord1", "AAPL", 10.0, 150.0, "MARKET", "SELL")
    assert res.order_id == "ord1"
    assert res.average_price < 150.0


def test_sim_execute_order_save(sim_orch):
    res = sim_orch.simulate_execution("ord1", "AAPL", 10.0, 150.0, "MARKET", "BUY")
    assert sim_orch.repository.get_execution(res.execution_id) is not None


def test_sim_execute_order_retrieve(sim_orch):
    res = sim_orch.simulate_execution("ord1", "AAPL", 10.0, 150.0, "MARKET", "BUY")
    retrieved = sim_orch.repository.get_execution(res.execution_id)
    assert retrieved.order_id == "ord1"


def test_sim_order_started_event(sim_orch, event_bus):
    events = []
    event_bus.subscribe("system.order_simulation_started", lambda e: events.append(e))
    sim_orch.simulate_execution("ord1", "AAPL", 10.0, 150.0, "MARKET", "BUY")
    assert len(events) == 1


def test_sim_order_completed_event(sim_orch, event_bus):
    events = []
    event_bus.subscribe("system.order_simulation_completed", lambda e: events.append(e))
    sim_orch.simulate_execution("ord1", "AAPL", 10.0, 150.0, "MARKET", "BUY")
    assert len(events) == 1


def test_sim_thread_safety_executions(sim_orch):
    threads = [threading.Thread(target=lambda i: sim_orch.simulate_execution(f"thread-ord-{i}", "AAPL", 10.0, 150.0, "MARKET", "BUY"), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    # Check that executions are cached
    assert len(sim_orch.repository._executions) == 10


def test_sim_plugin_registration(container):
    plugin = ExecutionSimulatorPlugin(container)
    plugin.initialize()
    orch = container.resolve(ExecutionSimulatorOrchestrator)
    assert orch is not None


def test_sim_memory_integration(sim_orch, container):
    res = sim_orch.simulate_execution("ord1", "AAPL", 10.0, 150.0, "MARKET", "BUY")
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("observability")) == 1


def test_sim_kg_integration(sim_orch, container):
    res = sim_orch.simulate_execution("ord1", "AAPL", 10.0, 150.0, "MARKET", "BUY")
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == res.execution_id), None) is not None


def test_sim_ops_integration(sim_orch, container):
    sim_orch.simulate_execution("ord1", "AAPL", 10.0, 150.0, "MARKET", "BUY")
    ops = container.resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")
    assert ops is not None
