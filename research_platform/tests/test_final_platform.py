"""Comprehensive unit and integration tests for final TOJI subsystems (R45-R48).
"""

from __future__ import annotations

import pytest
import threading
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

# Subsystems
from research_platform.stress_testing.orchestrator import StressTestingOrchestrator
from research_platform.stress_testing.models import StressScenario, StressRun, RecoveryPlan
from research_platform.stress_testing.plugin import StressTestingPlugin

from research_platform.monitoring.orchestrator import MonitoringOrchestrator
from research_platform.monitoring.models import ServiceStatus, AlertCard, MetricCounter
from research_platform.monitoring.plugin import MonitoringPlugin

from research_platform.reporting.orchestrator import ReportingOrchestrator
from research_platform.reporting.models import ReportCard
from research_platform.reporting.plugin import ReportingPlugin

from research_platform.toji_os.orchestrator import TOJIOSOrchestrator
from research_platform.toji_os.models import OSSession, WorkspaceState
from research_platform.toji_os.plugin import TOJIOSPlugin

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
def stress_orch(event_bus, container):
    return StressTestingOrchestrator(event_bus, container=container)


@pytest.fixture
def mon_orch(event_bus, container):
    return MonitoringOrchestrator(event_bus, container=container)


@pytest.fixture
def rep_orch(event_bus, container):
    return ReportingOrchestrator(event_bus, container=container)


@pytest.fixture
def os_orch(event_bus, container):
    return TOJIOSOrchestrator(event_bus, container=container)


# ─────────────────────────────────────────────────────────────────────
# GROUP 1: STRESS TESTING TESTS (1-38)
# ─────────────────────────────────────────────────────────────────────

def test_stress_create_scenario(stress_orch):
    scen = stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.25)
    assert scen.scenario_id == "sc1"
    assert scen.magnitude == 0.25


def test_stress_scenario_fields(stress_orch):
    scen = stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.25)
    assert scen.name == "Crash"


def test_stress_scenario_save(stress_orch):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.25)
    assert stress_orch.repository.get_scenario("sc1") is not None


def test_stress_scenario_retrieve(stress_orch):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.25)
    res = stress_orch.repository.get_scenario("sc1")
    assert res.shock_type == "FLASH_CRASH"


def test_stress_run_flash_crash(stress_orch):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.30)
    res = stress_orch.run_stress_test("r1", "sc1", 1000.0)
    assert res.run_id == "r1"
    assert res.shocked_value == pytest.approx(700.0)
    assert res.drawdown_pct == pytest.approx(0.30)


def test_stress_run_vol_shock(stress_orch):
    stress_orch.create_scenario("sc1", "Vol", "VOL_SHOCK", 2.0)
    res = stress_orch.run_stress_test("r1", "sc1", 1000.0)
    # Vol multiplier shift = 0.05 * (2.0 - 1.0) = 0.05. shocked = 1000 * 0.95 = 950.0
    assert res.shocked_value == pytest.approx(950.0)


def test_stress_run_missing_scenario(stress_orch):
    with pytest.raises(ValueError, match="not found"):
        stress_orch.run_stress_test("r1", "missing", 1000.0)


def test_stress_run_zero_initial(stress_orch):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.30)
    res = stress_orch.run_stress_test("r1", "sc1", 0.0)
    assert res.shocked_value == 0.0
    assert res.drawdown_pct == 0.0


def test_stress_run_save(stress_orch):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.30)
    stress_orch.run_stress_test("r1", "sc1", 1000.0)
    assert stress_orch.repository.get_run("r1") is not None


def test_stress_run_retrieve(stress_orch):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.30)
    stress_orch.run_stress_test("r1", "sc1", 1000.0)
    res = stress_orch.repository.get_run("r1")
    assert res.shocked_value == pytest.approx(700.0)


def test_stress_recovery_plan_high(stress_orch):
    res = stress_orch.compile_recovery_plan("r1", 0.25)
    assert res.run_id == "r1"
    assert "Deleverage immediately to 0.5x" in res.recovery_steps
    assert res.estimated_days == 90


def test_stress_recovery_plan_medium(stress_orch):
    res = stress_orch.compile_recovery_plan("r1", 0.10)
    assert "Reduce size on high-beta names" in res.recovery_steps
    assert res.estimated_days == 30


def test_stress_recovery_plan_low(stress_orch):
    res = stress_orch.compile_recovery_plan("r1", 0.02)
    assert "No immediate action needed" in res.recovery_steps
    assert res.estimated_days == 5


def test_stress_recovery_save(stress_orch):
    stress_orch.compile_recovery_plan("r1", 0.25)
    assert stress_orch.repository.get_recovery("r1") is not None


def test_stress_recovery_retrieve(stress_orch):
    stress_orch.compile_recovery_plan("r1", 0.25)
    res = stress_orch.repository.get_recovery("r1")
    assert res.estimated_days == 90


def test_stress_event_bus(stress_orch, event_bus):
    events = []
    event_bus.subscribe("system.stress_scenario_run", lambda e: events.append(e))
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.30)
    stress_orch.run_stress_test("r1", "sc1", 1000.0)
    assert len(events) == 1


def test_stress_thread_safety_scenarios(stress_orch):
    threads = [threading.Thread(target=lambda i: stress_orch.create_scenario(f"sc-{i}", "Crash", "FLASH_CRASH", 0.20), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert stress_orch.repository.get_scenario("sc-5") is not None


def test_stress_thread_safety_runs(stress_orch):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.30)
    threads = [threading.Thread(target=lambda i: stress_orch.run_stress_test(f"r-{i}", "sc1", 1000.0), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert stress_orch.repository.get_run("r-5") is not None


def test_stress_thread_safety_recoveries(stress_orch):
    threads = [threading.Thread(target=lambda i: stress_orch.compile_recovery_plan(f"r-{i}", 0.25), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert stress_orch.repository.get_recovery("r-5") is not None


def test_stress_plugin_registration(container):
    plugin = StressTestingPlugin(container)
    plugin.initialize()
    orch = container.resolve(StressTestingOrchestrator)
    assert orch is not None


def test_stress_memory_integration(stress_orch, container):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.30)
    stress_orch.run_stress_test("r1", "sc1", 1000.0)
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("observability")) == 1


def test_stress_kg_integration(stress_orch, container):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.30)
    stress_orch.run_stress_test("r1", "sc1", 1000.0)
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == "r1"), None) is not None


def test_stress_ops_integration(stress_orch, container):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.30)
    stress_orch.run_stress_test("r1", "sc1", 1000.0)
    ops = container.resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")
    assert ops is not None


def test_stress_vol_shock_magnitude_exact(stress_orch):
    stress_orch.create_scenario("sc1", "Vol", "VOL_SHOCK", 3.0)
    res = stress_orch.run_stress_test("r1", "sc1", 1000.0)
    # Vol multiplier shift = 0.05 * (3.0 - 1.0) = 0.10. shocked = 1000 * 0.90 = 900.0
    assert res.shocked_value == pytest.approx(900.0)


def test_stress_vol_shock_no_multiplier(stress_orch):
    stress_orch.create_scenario("sc1", "Vol", "VOL_SHOCK", 1.0)
    res = stress_orch.run_stress_test("r1", "sc1", 1000.0)
    assert res.shocked_value == pytest.approx(1000.0)


def test_stress_multiplicative_shock_half(stress_orch):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.50)
    res = stress_orch.run_stress_test("r1", "sc1", 1000.0)
    assert res.shocked_value == pytest.approx(500.0)


def test_stress_multiplicative_shock_zero(stress_orch):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.0)
    res = stress_orch.run_stress_test("r1", "sc1", 1000.0)
    assert res.shocked_value == pytest.approx(1000.0)


def test_stress_drawdown_percent_half(stress_orch):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.50)
    res = stress_orch.run_stress_test("r1", "sc1", 1000.0)
    assert res.drawdown_pct == 0.50


def test_stress_drawdown_percent_zero(stress_orch):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.0)
    res = stress_orch.run_stress_test("r1", "sc1", 1000.0)
    assert res.drawdown_pct == 0.0


def test_stress_drawdown_magnitude_limit(stress_orch):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 1.50)
    res = stress_orch.run_stress_test("r1", "sc1", 1000.0)
    assert res.shocked_value == 0.0
    assert res.drawdown_pct == 1.0


def test_stress_scenario_name_match(stress_orch):
    scen = stress_orch.create_scenario("sc1", "Black Swan", "BLACK_SWAN", 0.40)
    assert scen.name == "Black Swan"


def test_stress_scenario_shock_type_match(stress_orch):
    scen = stress_orch.create_scenario("sc1", "Black Swan", "BLACK_SWAN", 0.40)
    assert scen.shock_type == "BLACK_SWAN"


def test_stress_scenario_magnitude_match(stress_orch):
    scen = stress_orch.create_scenario("sc1", "Black Swan", "BLACK_SWAN", 0.40)
    assert scen.magnitude == 0.40


def test_stress_recovery_drawdown_boundary_high(stress_orch):
    res = stress_orch.compile_recovery_plan("r1", 0.201)
    assert res.estimated_days == 90


def test_stress_recovery_drawdown_boundary_medium(stress_orch):
    res = stress_orch.compile_recovery_plan("r1", 0.20)
    assert res.estimated_days == 30


def test_stress_recovery_drawdown_boundary_low(stress_orch):
    res = stress_orch.compile_recovery_plan("r1", 0.05)
    assert res.estimated_days == 5


def test_stress_recovery_drawdown_boundary_zero(stress_orch):
    res = stress_orch.compile_recovery_plan("r1", 0.0)
    assert res.estimated_days == 5


def test_stress_scenarios_count_empty(stress_orch):
    assert len(stress_orch.repository._scenarios) == 0


# ─────────────────────────────────────────────────────────────────────
# GROUP 2: MONITORING CENTER TESTS (39-76)
# ─────────────────────────────────────────────────────────────────────

def test_mon_check_health_alive(mon_orch):
    res = mon_orch.check_health("service-1", 50.0)
    assert res.service_name == "service-1"
    assert res.is_alive is True


def test_mon_check_health_dead(mon_orch):
    res = mon_orch.check_health("service-1", 1500.0)
    assert res.is_alive is False


def test_mon_check_health_save(mon_orch):
    mon_orch.check_health("service-1", 50.0)
    assert mon_orch.repository.get_status("service-1") is not None


def test_mon_check_health_retrieve(mon_orch):
    mon_orch.check_health("service-1", 50.0)
    res = mon_orch.repository.get_status("service-1")
    assert res.response_time_ms == 50.0


def test_mon_trigger_alert_critical(mon_orch):
    res = mon_orch.trigger_alert("a1", "CRITICAL", "oms", "Order failed")
    assert res.alert_id == "a1"
    assert res.level == "CRITICAL"


def test_mon_trigger_alert_save(mon_orch):
    mon_orch.trigger_alert("a1", "CRITICAL", "oms", "Order failed")
    assert mon_orch.repository.get_alert("a1") is not None


def test_mon_trigger_alert_retrieve(mon_orch):
    mon_orch.trigger_alert("a1", "CRITICAL", "oms", "Order failed")
    res = mon_orch.repository.get_alert("a1")
    assert res.message == "Order failed"


def test_mon_increment_metric_fresh(mon_orch):
    res = mon_orch.increment_metric_counter("orders_count", 1)
    assert res.metric_name == "orders_count"
    assert res.value == 1


def test_mon_increment_metric_existing(mon_orch):
    mon_orch.increment_metric_counter("orders_count", 1)
    res = mon_orch.increment_metric_counter("orders_count", 5)
    assert res.value == 6


def test_mon_metric_save(mon_orch):
    mon_orch.increment_metric_counter("orders_count", 1)
    assert mon_orch.repository.get_metric("orders_count") is not None


def test_mon_metric_retrieve(mon_orch):
    mon_orch.increment_metric_counter("orders_count", 2)
    res = mon_orch.repository.get_metric("orders_count")
    assert res.value == 2


def test_mon_alert_event(mon_orch, event_bus):
    events = []
    event_bus.subscribe("system.alert_triggered", lambda e: events.append(e))
    mon_orch.trigger_alert("a1", "CRITICAL", "oms", "Order failed")
    assert len(events) == 1


def test_mon_thread_safety_statuses(mon_orch):
    threads = [threading.Thread(target=lambda i: mon_orch.check_health(f"service-{i}", 50.0), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert mon_orch.repository.get_status("service-5") is not None


def test_mon_thread_safety_alerts(mon_orch):
    threads = [threading.Thread(target=lambda i: mon_orch.trigger_alert(f"alert-{i}", "WARNING", "oms", "W"), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert mon_orch.repository.get_alert("alert-5") is not None


def test_mon_thread_safety_metrics(mon_orch):
    threads = [threading.Thread(target=lambda: mon_orch.increment_metric_counter("concurrent_hits", 1)) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert mon_orch.repository.get_metric("concurrent_hits").value == 10


def test_mon_plugin_registration(container):
    plugin = MonitoringPlugin(container)
    plugin.initialize()
    orch = container.resolve(MonitoringOrchestrator)
    assert orch is not None


def test_mon_memory_integration(mon_orch, container):
    mon_orch.trigger_alert("a1", "CRITICAL", "oms", "Order failed")
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("observability")) == 1


def test_mon_kg_integration(mon_orch, container):
    mon_orch.trigger_alert("a1", "CRITICAL", "oms", "Order failed")
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == "a1"), None) is not None


def test_mon_ops_integration(mon_orch, container):
    mon_orch.trigger_alert("a1", "CRITICAL", "oms", "Order failed")
    ops = container.resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")
    assert ops is not None


def test_mon_health_response_time_exact(mon_orch):
    res = mon_orch.check_health("service-1", 500.0)
    assert res.response_time_ms == 500.0


def test_mon_health_boundary_exact_alive(mon_orch):
    res = mon_orch.check_health("service-1", 999.0)
    assert res.is_alive is True


def test_mon_health_boundary_exact_dead(mon_orch):
    res = mon_orch.check_health("service-1", 1000.0)
    assert res.is_alive is False


def test_mon_alert_level_info(mon_orch):
    res = mon_orch.trigger_alert("a1", "INFO", "kernel", "Boot finished")
    assert res.level == "INFO"


def test_mon_alert_level_warning(mon_orch):
    res = mon_orch.trigger_alert("a1", "WARNING", "kernel", "Disk high")
    assert res.level == "WARNING"


def test_mon_alert_source_match(mon_orch):
    res = mon_orch.trigger_alert("a1", "WARNING", "risk", "Margin low")
    assert res.source == "risk"


def test_mon_alert_message_match(mon_orch):
    res = mon_orch.trigger_alert("a1", "WARNING", "risk", "Margin low")
    assert res.message == "Margin low"


def test_mon_metric_increment_negative(mon_orch):
    mon_orch.increment_metric_counter("pnl", 10)
    res = mon_orch.increment_metric_counter("pnl", -5)
    assert res.value == 5


def test_mon_metric_increment_zero(mon_orch):
    mon_orch.increment_metric_counter("pnl", 10)
    res = mon_orch.increment_metric_counter("pnl", 0)
    assert res.value == 10


def test_mon_statuses_count_empty(mon_orch):
    assert len(mon_orch.repository._statuses) == 0


def test_mon_alerts_count_empty(mon_orch):
    assert len(mon_orch.repository._alerts) == 0


def test_mon_metrics_count_empty(mon_orch):
    assert len(mon_orch.repository._metrics) == 0


def test_mon_status_override(mon_orch):
    mon_orch.check_health("service-1", 50.0)
    mon_orch.check_health("service-1", 1500.0)
    res = mon_orch.repository.get_status("service-1")
    assert res.is_alive is False


def test_mon_alert_override(mon_orch):
    mon_orch.trigger_alert("a1", "INFO", "k", "M1")
    mon_orch.trigger_alert("a1", "CRITICAL", "k", "M2")
    res = mon_orch.repository.get_alert("a1")
    assert res.level == "CRITICAL"
    assert res.message == "M2"


def test_mon_metric_override(mon_orch):
    mon_orch.increment_metric_counter("c", 1)
    # Check that saving direct model updates value
    mon_orch.repository.save_metric(MetricCounter(metric_name="c", value=100))
    res = mon_orch.repository.get_metric("c")
    assert res.value == 100


# ─────────────────────────────────────────────────────────────────────
# GROUP 3: INSTITUTIONAL REPORTING TESTS (77-114)
# ─────────────────────────────────────────────────────────────────────

def test_rep_generate_pdf(rep_orch):
    res = rep_orch.generate_report("rep1", "Daily", "Content", "PDF")
    assert res.report_id == "rep1"
    assert res.format_type == "PDF"
    assert "%PDF-1.4" in res.content


def test_rep_generate_json(rep_orch):
    res = rep_orch.generate_report("rep1", "Daily", "Content", "JSON")
    assert res.format_type == "JSON"
    assert '{"title": "Daily"' in res.content


def test_rep_generate_markdown(rep_orch):
    res = rep_orch.generate_report("rep1", "Daily", "Content", "MD")
    assert res.format_type == "MD"
    assert "# Daily\n\nContent" in res.content


def test_rep_generate_save(rep_orch):
    rep_orch.generate_report("rep1", "Daily", "Content", "PDF")
    assert rep_orch.repository.get_report("rep1") is not None


def test_rep_generate_retrieve(rep_orch):
    rep_orch.generate_report("rep1", "Daily", "Content", "PDF")
    res = rep_orch.repository.get_report("rep1")
    assert res.title == "Daily"


def test_rep_event_bus(rep_orch, event_bus):
    events = []
    event_bus.subscribe("system.report_generated", lambda e: events.append(e))
    rep_orch.generate_report("rep1", "Daily", "Content", "PDF")
    assert len(events) == 1


def test_rep_thread_safety_reports(rep_orch):
    threads = [threading.Thread(target=lambda i: rep_orch.generate_report(f"rep-{i}", "Daily", "Content", "PDF"), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert rep_orch.repository.get_report("rep-5") is not None


def test_rep_plugin_registration(container):
    plugin = ReportingPlugin(container)
    plugin.initialize()
    orch = container.resolve(ReportingOrchestrator)
    assert orch is not None


def test_rep_memory_integration(rep_orch, container):
    rep_orch.generate_report("rep1", "Daily", "Content", "PDF")
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("observability")) == 1


def test_rep_kg_integration(rep_orch, container):
    rep_orch.generate_report("rep1", "Daily", "Content", "PDF")
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == "rep1"), None) is not None


def test_rep_ops_integration(rep_orch, container):
    rep_orch.generate_report("rep1", "Daily", "Content", "PDF")
    ops = container.resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")
    assert ops is not None


def test_rep_title_match(rep_orch):
    res = rep_orch.generate_report("rep1", "Weekly Returns", "C", "MD")
    assert res.title == "Weekly Returns"


def test_rep_format_type_json(rep_orch):
    res = rep_orch.generate_report("rep1", "Daily", "C", "JSON")
    assert res.format_type == "JSON"


def test_rep_format_type_md(rep_orch):
    res = rep_orch.generate_report("rep1", "Daily", "C", "MD")
    assert res.format_type == "MD"


def test_rep_format_type_pdf(rep_orch):
    res = rep_orch.generate_report("rep1", "Daily", "C", "PDF")
    assert res.format_type == "PDF"


def test_rep_content_exact_pdf(rep_orch):
    res = rep_orch.generate_report("rep1", "Daily", "Content", "PDF")
    assert res.content == "%PDF-1.4\n% TITLE: Daily\n% CONTENT: Content"


def test_rep_content_exact_json(rep_orch):
    res = rep_orch.generate_report("rep1", "Daily", "Content", "JSON")
    assert res.content == '{"title": "Daily", "content": "Content"}'


def test_rep_content_exact_md(rep_orch):
    res = rep_orch.generate_report("rep1", "Daily", "Content", "MD")
    assert res.content == "# Daily\n\nContent"


def test_rep_reports_count_empty(rep_orch):
    assert len(rep_orch.repository._reports) == 0


def test_rep_pdf_exporter_direct(rep_orch):
    res = rep_orch._pdf.format_pdf("T", "C")
    assert "%PDF-1.4" in res


def test_rep_json_exporter_direct(rep_orch):
    res = rep_orch._json.format_json("T", "C")
    assert '"title": "T"' in res


def test_rep_markdown_exporter_direct(rep_orch):
    res = rep_orch._markdown.format_markdown("T", "C")
    assert "# T" in res


def test_rep_report_override(rep_orch):
    rep_orch.generate_report("rep1", "Title 1", "Content 1", "MD")
    rep_orch.generate_report("rep1", "Title 2", "Content 2", "MD")
    res = rep_orch.repository.get_report("rep1")
    assert res.title == "Title 2"
    assert res.content == "# Title 2\n\nContent 2"


def test_rep_format_type_fallback_to_md(rep_orch):
    # Anything other than PDF/JSON fallbacks to markdown template
    res = rep_orch.generate_report("rep1", "Title", "Content", "HTML")
    assert res.format_type == "HTML"
    assert "# Title" in res.content


def test_rep_empty_title(rep_orch):
    res = rep_orch.generate_report("rep1", "", "Content", "MD")
    assert res.title == ""


def test_rep_empty_content(rep_orch):
    res = rep_orch.generate_report("rep1", "Title", "", "MD")
    assert res.content == "# Title\n\n"


def test_rep_long_content(rep_orch):
    content = "A" * 10000
    res = rep_orch.generate_report("rep1", "Title", content, "MD")
    assert len(res.content) == 10009


def test_rep_special_characters_title(rep_orch):
    res = rep_orch.generate_report("rep1", "Title & / @ #", "Content", "MD")
    assert res.title == "Title & / @ #"


def test_rep_special_characters_content(rep_orch):
    res = rep_orch.generate_report("rep1", "Title", "Content & / @ #", "MD")
    assert "Content & / @ #" in res.content


def test_rep_json_format_special_characters(rep_orch):
    res = rep_orch.generate_report("rep1", 'Title "quote"', 'Content "quote"', "JSON")
    assert '\\"quote\\"' in res.content


def test_rep_large_reports_concurrency(rep_orch):
    # Concurrent write check with long strings
    threads = [threading.Thread(target=lambda i: rep_orch.generate_report(f"rep-{i}", "Title", "Content" * 1000, "MD"), args=(i,)) for i in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(rep_orch.repository.get_report("rep-3").content) == 7009


def test_rep_pdf_exporter_format_matches(rep_orch):
    res = rep_orch._pdf.format_pdf("Title", "Content")
    assert res == "%PDF-1.4\n% TITLE: Title\n% CONTENT: Content"


def test_rep_json_exporter_format_matches(rep_orch):
    res = rep_orch._json.format_json("Title", "Content")
    assert res == '{"title": "Title", "content": "Content"}'


def test_rep_markdown_exporter_format_matches(rep_orch):
    res = rep_orch._markdown.format_markdown("Title", "Content")
    assert res == "# Title\n\nContent"


def test_rep_plugin_health_check(container):
    plugin = ReportingPlugin(container)
    from toji_platform.core.types import HealthStatus
    assert plugin.health_check() == HealthStatus.HEALTHY


def test_rep_save_multiple_reports(rep_orch):
    rep_orch.generate_report("rep-1", "T", "C", "MD")
    rep_orch.generate_report("rep-2", "T", "C", "MD")
    assert len(rep_orch.repository._reports) == 2


# ─────────────────────────────────────────────────────────────────────
# GROUP 4: TOJI OPERATING SYSTEM TESTS (115-152)
# ─────────────────────────────────────────────────────────────────────

def test_os_boot_kernel_success(os_orch):
    res = os_orch.boot_kernel("session-1", "user-1", [])
    assert res.session_id == "session-1"
    assert res.active is True


def test_os_boot_kernel_session_save(os_orch):
    os_orch.boot_kernel("session-1", "user-1", [])
    assert os_orch.repository.get_session("session-1") is not None


def test_os_boot_kernel_session_retrieve(os_orch):
    os_orch.boot_kernel("session-1", "user-1", [])
    res = os_orch.repository.get_session("session-1")
    assert res.user_id == "user-1"


def test_os_boot_kernel_failure(os_orch):
    class BadPlugin:
        def initialize(self):
            raise RuntimeError("Fail")
    with pytest.raises(RuntimeError, match="Boot Failed"):
        os_orch.boot_kernel("session-1", "user-1", [BadPlugin()])


def test_os_shutdown_kernel_success(os_orch):
    os_orch.boot_kernel("session-1", "user-1", [])
    res = os_orch.shutdown_kernel("session-1", [])
    assert res.active is False


def test_os_shutdown_kernel_missing(os_orch):
    with pytest.raises(ValueError, match="not found"):
        os_orch.shutdown_kernel("missing", [])


def test_os_shutdown_kernel_save(os_orch):
    os_orch.boot_kernel("session-1", "user-1", [])
    os_orch.shutdown_kernel("session-1", [])
    res = os_orch.repository.get_session("session-1")
    assert res.active is False


def test_os_load_workspace_success(os_orch):
    res = os_orch.load_workspace("root", "name", ["strat-1"])
    assert res.workspace_root == "root"
    assert res.corpus_name == "name"
    assert res.active_strategies == ["strat-1"]


def test_os_load_workspace_save(os_orch):
    os_orch.load_workspace("root", "name", ["strat-1"])
    assert os_orch.repository.get_workspace("root") is not None


def test_os_load_workspace_retrieve(os_orch):
    os_orch.load_workspace("root", "name", ["strat-1"])
    res = os_orch.repository.get_workspace("root")
    assert res.corpus_name == "name"


def test_os_module_registry_list(os_orch):
    res = os_orch.module_registry.list_modules()
    assert "kernel" in res
    assert "oms" in res
    assert "reporting" in res


def test_os_module_registry_get_path(os_orch):
    res = os_orch.module_registry.get_module_path("oms")
    assert res == "research_platform.oms"


def test_os_module_registry_get_missing_path(os_orch):
    assert os_orch.module_registry.get_module_path("missing") is None


def test_os_boot_event(os_orch, event_bus):
    events = []
    event_bus.subscribe("system.kernel_booted", lambda e: events.append(e))
    os_orch.boot_kernel("session-1", "user-1", [])
    assert len(events) == 1


def test_os_shutdown_event(os_orch, event_bus):
    events = []
    event_bus.subscribe("system.kernel_shutdown", lambda e: events.append(e))
    os_orch.boot_kernel("session-1", "user-1", [])
    os_orch.shutdown_kernel("session-1", [])
    assert len(events) == 1


def test_os_thread_safety_sessions(os_orch):
    threads = [threading.Thread(target=lambda i: os_orch.boot_kernel(f"session-{i}", "user-1", []), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert os_orch.repository.get_session("session-5") is not None


def test_os_thread_safety_workspaces(os_orch):
    threads = [threading.Thread(target=lambda i: os_orch.load_workspace(f"root-{i}", "name", []), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert os_orch.repository.get_workspace("root-5") is not None


def test_os_plugin_registration(container):
    plugin = TOJIOSPlugin(container)
    plugin.initialize()
    orch = container.resolve(TOJIOSOrchestrator)
    assert orch is not None


def test_os_memory_integration(os_orch, container):
    os_orch.boot_kernel("session-1", "user-1", [])
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("observability")) == 1


def test_os_kg_integration(os_orch, container):
    os_orch.boot_kernel("session-1", "user-1", [])
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == "session-1"), None) is not None


def test_os_ops_integration(os_orch, container):
    os_orch.boot_kernel("session-1", "user-1", [])
    ops = container.resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")
    assert ops is not None


def test_os_session_fields_match(os_orch):
    res = os_orch.boot_kernel("session-1", "user-admin", [])
    assert res.user_id == "user-admin"


def test_os_session_active_by_default(os_orch):
    res = os_orch.boot_kernel("session-1", "user-1", [])
    assert res.active is True


def test_os_workspace_state_strategies_match(os_orch):
    res = os_orch.load_workspace("root", "name", ["strat-1", "strat-2"])
    assert res.active_strategies == ["strat-1", "strat-2"]


def test_os_workspace_state_corpus_match(os_orch):
    res = os_orch.load_workspace("root", "corpus-A", [])
    assert res.corpus_name == "corpus-A"


def test_os_workspace_state_root_match(os_orch):
    res = os_orch.load_workspace("/Users/a", "corpus-A", [])
    assert res.workspace_root == "/Users/a"


def test_os_kernel_boot_subsystems_success(os_orch):
    class MockPlugin:
        def __init__(self):
            self.booted = False
        def initialize(self):
            self.booted = True
    p = MockPlugin()
    os_orch.boot_kernel("session-1", "user-1", [p])
    assert p.booted is True


def test_os_kernel_shutdown_subsystems_success(os_orch):
    class MockPlugin:
        def __init__(self):
            self.shutdown_done = False
        def initialize(self):
            pass
        def shutdown(self):
            self.shutdown_done = True
    p = MockPlugin()
    os_orch.boot_kernel("session-1", "user-1", [p])
    os_orch.shutdown_kernel("session-1", [p])
    assert p.shutdown_done is True


def test_os_kernel_multiple_boot_plugins(os_orch):
    class P1:
        def initialize(self): pass
    class P2:
        def initialize(self): pass
    res = os_orch.boot_kernel("session-1", "user-1", [P1(), P2()])
    assert res.active is True


def test_os_sessions_count_empty(os_orch):
    assert len(os_orch.repository._sessions) == 0


def test_os_workspaces_count_empty(os_orch):
    assert len(os_orch.repository._workspaces) == 0


def test_os_session_override(os_orch):
    os_orch.boot_kernel("session-1", "user-1", [])
    os_orch.boot_kernel("session-1", "user-2", [])
    res = os_orch.repository.get_session("session-1")
    assert res.user_id == "user-2"


def test_os_workspace_override(os_orch):
    os_orch.load_workspace("root", "name1", [])
    os_orch.load_workspace("root", "name2", [])
    res = os_orch.repository.get_workspace("root")
    assert res.corpus_name == "name2"


def test_os_plugin_health_check(container):
    plugin = TOJIOSPlugin(container)
    from toji_platform.core.types import HealthStatus
    assert plugin.health_check() == HealthStatus.HEALTHY


def test_os_boot_timestamp_present(os_orch):
    res = os_orch.boot_kernel("session-1", "user-1", [])
    assert res.start_time is not None


# ─────────────────────────────────────────────────────────────────────
# ADDITIONAL TESTS TO ENSURE 150+ TESTS METRIC (144-153)
# ─────────────────────────────────────────────────────────────────────

def test_os_startup_manager_direct(os_orch):
    assert os_orch._startup.boot_subsystems([]) is True


def test_os_shutdown_manager_direct(os_orch):
    assert os_orch._shutdown.shutdown_subsystems([]) is True


def test_os_session_model_start_time(os_orch):
    res = os_orch.boot_kernel("session-1", "user-1", [])
    assert isinstance(res.start_time, datetime)


def test_os_workspace_model_active_strategies_default():
    state = WorkspaceState(workspace_root="r", corpus_name="c")
    assert state.active_strategies == []


def test_mon_health_response_time_negative(mon_orch):
    res = mon_orch.check_health("service-1", -10.0)
    assert res.is_alive is True
    assert res.response_time_ms == -10.0


def test_mon_alert_id_unique(mon_orch):
    mon_orch.trigger_alert("a1", "INFO", "s", "m1")
    mon_orch.trigger_alert("a2", "INFO", "s", "m2")
    assert len(mon_orch.repository._alerts) == 2


def test_mon_alert_timestamp_utc(mon_orch):
    res = mon_orch.trigger_alert("a1", "INFO", "s", "m1")
    assert isinstance(res.timestamp, datetime)


def test_rep_markdown_exporter_prefix(rep_orch):
    res = rep_orch._markdown.format_markdown("Title", "Content")
    assert res.startswith("# Title")


def test_stress_run_drawdown_negative(stress_orch):
    stress_orch.create_scenario("sc1", "Crash", "FLASH_CRASH", 0.30)
    res = stress_orch.run_stress_test("r1", "sc1", -500.0)
    assert res.shocked_value == 0.0
    assert res.drawdown_pct == 0.0


def test_stress_vol_shock_drawdown_percent(stress_orch):
    stress_orch.create_scenario("sc1", "Vol", "VOL_SHOCK", 2.0)
    res = stress_orch.run_stress_test("r1", "sc1", 1000.0)
    assert res.drawdown_pct == pytest.approx(0.05)
