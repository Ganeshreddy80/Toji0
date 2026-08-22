"""Unit tests for PortfolioConstructionPlugin."""

from __future__ import annotations

from unittest.mock import MagicMock
from portfolio_construction.core.plugin import PortfolioConstructionPlugin
from toji_platform.core.types import HealthStatus, ModuleState


def test_plugin_metadata_and_lifecycle():
    mock_event_bus = MagicMock()
    plugin = PortfolioConstructionPlugin(event_bus=mock_event_bus)

    assert plugin.name == "Portfolio Construction Engine"
    assert plugin.version == "1.0.0"
    assert str(plugin.plugin_id) == "portfolio_construction"
    assert plugin.state == ModuleState.CREATED

    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING
    assert plugin.health_check() == HealthStatus.HEALTHY

    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED
