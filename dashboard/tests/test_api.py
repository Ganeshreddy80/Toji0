import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from dashboard.core.models import DashboardSnapshot, HistoricalEvent
from dashboard.core.state import DashboardStateStore
from dashboard.core.repository import DashboardRepository
from dashboard.core.orchestrator import DashboardOrchestrator
from dashboard.health.health_monitor import HealthMonitor
from dashboard.websocket.websocket_manager import WebSocketManager
from dashboard.aggregator.event_aggregator import DashboardEventAggregator
from dashboard.backend.app import create_app


@pytest.fixture
def test_env() -> tuple[TestClient, DashboardStateStore, DashboardEventAggregator]:
    """Initialize standard app components with mock inputs."""
    from toji_platform.core.dependency_injection.container import Container
    from toji_platform.core.configuration.interfaces import IConfigProvider
    from toji_platform.core.configuration.manager import ConfigurationManager
    from risk_engine.core.interfaces import IRiskStateStore
    from risk_engine.core.state import RiskStateStore

    state_store = DashboardStateStore()
    repository = DashboardRepository()
    health_monitor = HealthMonitor()
    websocket_manager = WebSocketManager()
    
    orchestrator = DashboardOrchestrator()
    orchestrator.initialize(state_store, repository)
    
    event_aggregator = DashboardEventAggregator(
        orchestrator=orchestrator,
        health_monitor=health_monitor,
        websocket_manager=websocket_manager,
    )
    
    # Initialize container with mock services for new risk endpoints
    container = Container()
    config_mgr = ConfigurationManager()
    risk_store = RiskStateStore()
    container.register(IConfigProvider, instance=config_mgr)
    container.register(IRiskStateStore, instance=risk_store)

    app = create_app(
        state_store=state_store,
        repository=repository,
        health_monitor=health_monitor,
        websocket_manager=websocket_manager,
        event_aggregator=event_aggregator,
        container=container,
    )
    
    client = TestClient(app)
    client.container = container
    client.risk_store = risk_store
    client.config_mgr = config_mgr
    return client, state_store, event_aggregator


def test_api_health_endpoint(test_env: tuple[TestClient, DashboardStateStore, DashboardEventAggregator]) -> None:
    """Test health REST endpoint returning system diagnostics state."""
    client, _, _ = test_env
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "MIL" in data
    assert data["MIL"]["status"] == "Initializing"



def test_api_dashboard_snapshots_endpoint(test_env: tuple[TestClient, DashboardStateStore, DashboardEventAggregator]) -> None:
    """Test dashboard snapshots REST endpoint with symbol and timeframe filters."""
    client, state_store, _ = test_env

    # Empty store
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert response.json() == []

    # Insert mock snapshot
    snapshot = DashboardSnapshot(
        snapshot_id="snap-111",
        symbol="BTC/USDT",
        timeframe="1h",
        market_state={"trend": "BULLISH"},
        pattern_state={"patterns": ["double_top"]},
        confluence={"score": 85.0},
        strategy={"signal": "BUY"},
        risk_assessment={"decision": "permit"},
        position_size={"quantity": 1.5},
        health_status={},
    )
    state_store.update_snapshot(snapshot)

    # Fetch all
    response = client.get("/dashboard")
    assert len(response.json()) == 1
    assert response.json()[0]["symbol"] == "BTC/USDT"

    # Filter match
    response = client.get("/dashboard?symbol=BTC/USDT&timeframe=1h")
    assert response.status_code == 200
    assert response.json()["snapshot_id"] == "snap-111"

    # Filter miss
    response = client.get("/dashboard?symbol=ETH/USDT")
    assert response.json() == []


def test_api_specific_subsystem_endpoints(test_env: tuple[TestClient, DashboardStateStore, DashboardEventAggregator]) -> None:
    """Verify separate endpoints for market state, patterns, confluence, etc."""
    client, state_store, _ = test_env

    snapshot = DashboardSnapshot(
        snapshot_id="snap-111",
        symbol="BTC/USDT",
        timeframe="1h",
        market_state={"trend": "BULLISH"},
        pattern_state={"patterns": ["double_top"]},
        confluence={"score": 85.0},
        strategy={"signal": "BUY"},
        risk_assessment={"decision": "permit"},
        position_size={"quantity": 1.5},
        health_status={},
    )
    state_store.update_snapshot(snapshot)

    # Market state
    res = client.get("/market")
    assert len(res.json()) == 1
    assert res.json()[0]["market_state"] == {"trend": "BULLISH"}

    # Patterns
    res = client.get("/patterns")
    assert res.json()[0]["pattern_state"] == {"patterns": ["double_top"]}

    # Confluence
    res = client.get("/confluence")
    assert res.json()[0]["confluence"] == {"score": 85.0}

    # Strategy
    res = client.get("/strategy")
    assert res.json()[0]["strategy"] == {"signal": "BUY"}

    # Risk
    res = client.get("/risk")
    assert res.json()[0]["risk_assessment"] == {"decision": "permit"}

    # Position sizing
    res = client.get("/position-size")
    assert res.json()[0]["position_size"] == {"quantity": 1.5}


def test_api_events_timeline_endpoint(test_env: tuple[TestClient, DashboardStateStore, DashboardEventAggregator]) -> None:
    """Verify events timeline endpoint lists timeline logs chronologically."""
    client, _, event_aggregator = test_env

    # Empty history
    res = client.get("/events")
    assert res.json() == []

    # Insert timeline logs
    evt1 = HistoricalEvent(
        event_id="evt-1",
        timestamp=datetime.now(timezone.utc),
        subsystem="MIL",
        event_name="MarketStateUpdated",
        symbol="BTC/USDT",
        timeframe="1h",
        latency_ms=5.0,
        severity="info",
        payload={},
    )
    event_aggregator.add_historical_event(evt1)

    res = client.get("/events")
    assert len(res.json()) == 1
    assert res.json()[0]["event_id"] == "evt-1"


def test_api_executions_health(test_env: tuple[TestClient, DashboardStateStore, DashboardEventAggregator]) -> None:
    """Verify execution health endpoint."""
    client, _, _ = test_env
    res = client.get("/executions/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"


def test_api_portfolio_endpoints(test_env: tuple[TestClient, DashboardStateStore, DashboardEventAggregator]) -> None:
    """Verify portfolio endpoints do not return 500 when empty/no data."""
    client, _, _ = test_env
    
    # 1. /portfolio/snapshot
    res_snap = client.get("/portfolio/snapshot")
    assert res_snap.status_code == 200
    snap_data = res_snap.json()
    assert snap_data["snapshot_id"] is not None
    assert "metrics" in snap_data
    
    # 2. /portfolio/positions
    res_pos = client.get("/portfolio/positions")
    assert res_pos.status_code == 200
    pos_data = res_pos.json()
    assert "open" in pos_data
    assert "closed" in pos_data
    
    # 3. /portfolio/metrics
    res_metrics = client.get("/portfolio/metrics")
    assert res_metrics.status_code == 200
    metrics_data = res_metrics.json()
    assert "metrics" in metrics_data
    assert "health" in metrics_data
    assert "statistics" in metrics_data


def test_api_risk_endpoints(test_env: tuple[TestClient, DashboardStateStore, DashboardEventAggregator]) -> None:
    """Verify Sprint 7 risk REST API endpoints."""
    client, _, _ = test_env
    
    # 1. /api/v1/risk/status (when empty)
    res = client.get("/api/v1/risk/status")
    assert res.status_code == 200
    assert res.json() == []

    # Insert dummy risk snapshot
    from risk_engine.core.models import RiskSnapshot, RiskState, RiskAssessment, AccountRisk, DrawdownRisk, ExposureRisk, LeverageRisk, CircuitBreakerState
    from risk_engine.core.enums import RiskDecision
    from datetime import datetime, timezone
    
    now = datetime.now(timezone.utc)
    assessment = RiskAssessment(
        overall_score=100.0,
        decision=RiskDecision.ALLOW,
        violations=[]
    )
    rstate = RiskState(
        symbol="BTC/USDT",
        timeframe="1m",
        assessment=assessment,
        account_risk=AccountRisk(leverage=1.0, margin_utilization=0.01),
        drawdown_risk=DrawdownRisk(max_drawdown_limit=0.1, current_drawdown=0.0, drawdown_limit_breached=False),
        exposure_risk=ExposureRisk(max_exposure_limit=0.5, current_exposure=0.0, exposure_limit_breached=False),
        leverage_risk=LeverageRisk(max_leverage_limit=10.0, current_leverage=1.0, leverage_limit_breached=False),
        circuit_breaker=CircuitBreakerState(halt_trading=False, cooldown_until=None)
    )
    
    snap = RiskSnapshot(
        snapshot_id="risk-snap-111",
        symbol="BTC/USDT",
        timestamp=now,
        states={"1m": rstate}
    )
    client.risk_store.update_snapshot(snap)

    # Recheck /api/v1/risk/status
    res = client.get("/api/v1/risk/status")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["symbol"] == "BTC/USDT"

    # 2. /api/v1/risk/breakers
    res_breakers = client.get("/api/v1/risk/breakers")
    assert res_breakers.status_code == 200
    breakers_data = res_breakers.json()
    assert "BTC/USDT:1m" in breakers_data
    assert breakers_data["BTC/USDT:1m"]["halt_trading"] is False

    # 3. /api/v1/risk/killswitch
    assert client.config_mgr.get("risk.emergency_stop") is None
    res_kill = client.post("/api/v1/risk/killswitch")
    assert res_kill.status_code == 200
    assert res_kill.json()["status"] == "triggered"
    assert client.config_mgr.get("risk.emergency_stop") is True
    assert client.config_mgr.get("risk.manual_kill_switch") is True

    # 4. /api/v1/risk/override
    assert client.config_mgr.get("risk.risk_override") is None
    res_override = client.post("/api/v1/risk/override?enable=true")
    assert res_override.status_code == 200
    assert res_override.json()["override_active"] is True
    assert client.config_mgr.get("risk.risk_override") is True

