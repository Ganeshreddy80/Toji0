"""Comprehensive unit and integration tests for R54 Alerting & Notification Subsystem.
"""

from __future__ import annotations

import pytest
import unittest.mock
from datetime import datetime, timezone, timedelta

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.alerting.models import Alert, AlertRule, AlertSeverity, AlertChannel, AlertStatus
from research_platform.alerting.repository import AlertRepository
from research_platform.alerting.rule_engine import AlertRuleEngine
from research_platform.alerting.dispatcher import AlertDispatcher
from research_platform.alerting.orchestrator import AlertOrchestrator
from research_platform.alerting.plugin import AlertingPlugin


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def container(event_bus):
    c = Container()
    c.register("IEventBus", instance=event_bus)
    return c


class TestAlertingModels:
    def test_alert_defaults(self):
        alert = Alert(title="Test Alert", message="System overloaded", severity=AlertSeverity.HIGH)
        assert alert.alert_id is not None
        assert alert.status == AlertStatus.PENDING
        assert len(alert.channels) == 1
        assert alert.channels[0] == AlertChannel.LOG
        assert alert.created_at is not None

    def test_alert_rule_defaults(self):
        rule = AlertRule(name="CPU_Rule", description="Alert on high CPU")
        assert rule.rule_id is not None
        assert rule.cooldown_sec == 300.0
        assert rule.enabled is True
        assert rule.fire_count == 0


class TestAlertRepository:
    def test_save_and_retrieve(self):
        repo = AlertRepository()
        alert = Alert(title="A", message="B", severity=AlertSeverity.INFO)
        repo.save(alert)
        assert repo.count() == 1
        
        recent = repo.get_recent(5)
        assert len(recent) == 1
        assert recent[0].title == "A"

    def test_acknowledge(self):
        repo = AlertRepository()
        alert = Alert(title="A", message="B", severity=AlertSeverity.INFO)
        repo.save(alert)
        
        assert len(repo.get_unacknowledged()) == 1
        
        acked = repo.acknowledge(alert.alert_id)
        assert acked is True
        assert len(repo.get_unacknowledged()) == 0
        assert repo.get_recent()[0].status == AlertStatus.ACKNOWLEDGED
        assert repo.get_recent()[0].acknowledged_at is not None

    def test_get_by_severity(self):
        repo = AlertRepository()
        alert_info = Alert(title="I", message="msg", severity=AlertSeverity.INFO)
        alert_crit = Alert(title="C", message="msg", severity=AlertSeverity.CRITICAL)
        repo.save(alert_info)
        repo.save(alert_crit)
        
        crits = repo.get_by_severity("CRITICAL")
        assert len(crits) == 1
        assert crits[0].title == "C"


class TestAlertRuleEngine:
    def test_builtin_rules_evaluate(self):
        engine = AlertRuleEngine()
        
        # Test validation cert failure
        fired = engine.evaluate({"certified": False})
        assert len(fired) == 1
        assert fired[0].title == "ValidationCertificationFailed"
        assert fired[0].severity == AlertSeverity.HIGH
        
        # Test CPU rule
        fired_cpu = engine.evaluate({"cpu_pct": 90.0})
        assert len(fired_cpu) == 1
        assert fired_cpu[0].title == "HighCPUUsage"

        # Test Drawdown rule
        fired_dd = engine.evaluate({"drawdown_pct": 0.10})
        assert len(fired_dd) == 1
        assert fired_dd[0].title == "DrawdownThresholdBreached"
        assert fired_dd[0].severity == AlertSeverity.CRITICAL

    def test_cooldown_behavior(self):
        engine = AlertRuleEngine()
        
        # Trigger validation failure rule
        fired_first = engine.evaluate({"certified": False})
        assert len(fired_first) == 1
        
        # Try triggering immediately again — should be cooled down
        fired_second = engine.evaluate({"certified": False})
        assert len(fired_second) == 0

    def test_custom_rule(self):
        engine = AlertRuleEngine()
        custom_rule = AlertRule(name="CustomRule", cooldown_sec=1.0)
        engine.add_rule(custom_rule, handler=lambda r, ctx: ctx.get("value", 0) > 10)
        
        fired = engine.evaluate({"value": 15})
        assert len(fired) == 1
        assert fired[0].title == "CustomRule"


class TestAlertDispatcher:
    def test_dispatch_log_channel(self):
        repo = AlertRepository()
        dispatcher = AlertDispatcher(repository=repo)
        
        alert = Alert(title="Test", message="Log msg", severity=AlertSeverity.LOW, channels=[AlertChannel.LOG])
        results = dispatcher.dispatch(alert)
        
        assert len(results) == 1
        assert results[0].success is True
        assert alert.status == AlertStatus.SENT

    def test_webhook_channel_success(self):
        repo = AlertRepository()
        dispatcher = AlertDispatcher(repository=repo, webhook_url="http://mock-webhook")
        
        alert = Alert(title="Test Webhook", message="Web msg", severity=AlertSeverity.INFO, channels=[AlertChannel.WEBHOOK])
        
        with unittest.mock.patch("urllib.request.urlopen") as mock_urlopen:
            results = dispatcher.dispatch(alert)
            assert len(results) == 1
            assert results[0].success is True
            assert alert.status == AlertStatus.SENT
            mock_urlopen.assert_called_once()

    def test_webhook_channel_missing_url(self):
        repo = AlertRepository()
        dispatcher = AlertDispatcher(repository=repo, webhook_url="")
        
        alert = Alert(title="Test Webhook", message="Web msg", severity=AlertSeverity.INFO, channels=[AlertChannel.WEBHOOK])
        results = dispatcher.dispatch(alert)
        assert len(results) == 1
        assert results[0].success is False
        assert alert.status == AlertStatus.FAILED


class TestAlertOrchestrator:
    def test_orchestrator_flow(self):
        orchestrator = AlertOrchestrator()
        
        # Fire manual alert
        alert = orchestrator.fire_simple("EnginePanic", "Strategy crashed", AlertSeverity.CRITICAL, channels=[AlertChannel.LOG])
        assert alert.status == AlertStatus.SENT
        
        recent = orchestrator.get_recent(10)
        assert len(recent) == 1
        assert recent[0].title == "EnginePanic"
        
        unacknowledged = orchestrator.get_unacknowledged()
        assert len(unacknowledged) == 1
        
        # Acknowledge
        success = orchestrator.acknowledge(alert.alert_id)
        assert success is True
        assert len(orchestrator.get_unacknowledged()) == 0

    def test_evaluate_context_fires_alert(self):
        orchestrator = AlertOrchestrator()
        fired = orchestrator.evaluate_context({"cpu_pct": 99.0})
        assert len(fired) == 1
        assert fired[0].title == "HighCPUUsage"
        
        recent = orchestrator.get_recent(5)
        assert len(recent) == 1
        assert recent[0].status == AlertStatus.SENT


class TestAlertingPlugin:
    def test_plugin_initialize(self, container):
        plugin = AlertingPlugin(container)
        plugin.initialize()
        
        orchestrator = container.resolve("AlertOrchestrator")
        assert orchestrator is not None
        assert isinstance(orchestrator, AlertOrchestrator)
        
        repository = container.resolve("AlertRepository")
        assert repository is not None
        assert isinstance(repository, AlertRepository)
        
        assert plugin.health_check() == "HEALTHY"
        plugin.shutdown()
