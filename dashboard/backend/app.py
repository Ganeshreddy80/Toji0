"""FastAPI Application factory for the Dashboard Platform."""

from __future__ import annotations

import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse

from dashboard.core.interfaces import IDashboardRepository, IDashboardStateStore
from dashboard.health.health_monitor import HealthMonitor
from dashboard.websocket.websocket_manager import WebSocketManager
from dashboard.aggregator.event_aggregator import DashboardEventAggregator
from dashboard.api.router import create_api_router


def create_app(
    state_store: IDashboardStateStore,
    repository: IDashboardRepository,
    health_monitor: HealthMonitor,
    websocket_manager: WebSocketManager,
    event_aggregator: DashboardEventAggregator,
    container: Any | None = None,
) -> FastAPI:
    """FastAPI application factory, injecting state and service layers."""
    app = FastAPI(
        title="Toji Dashboard API",
        version="1.0.0",
        description="REST and WebSocket API for quantitative platform observability.",
    )

    # Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Attach REST API router
    api_router = create_api_router(
        state_store=state_store,
        repository=repository,
        health_monitor=health_monitor,
        event_aggregator=event_aggregator,
        container=container,
    )
    app.include_router(api_router)

    # WebSocket connection endpoint
    @app.websocket("/ws/{channel}")
    async def websocket_endpoint(websocket: WebSocket, channel: str) -> None:
        """Handle incoming WebSocket connections mapped to updates channels."""
        await websocket_manager.connect(websocket, channel)
        try:
            while True:
                # Keep connection alive; accept any inbound messages (e.g. pings/sub-updates)
                data = await websocket.receive_text()
                await websocket.send_json({"echo": data, "channel": channel})
        except WebSocketDisconnect:
            websocket_manager.disconnect(websocket, channel)
        except Exception:
            websocket_manager.disconnect(websocket, channel)

    # Expose root index page to serve the React single-page UI
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    index_path = os.path.join(frontend_dir, "index.html")

    @app.get("/", response_class=HTMLResponse)
    async def get_index() -> HTMLResponse:
        """Serve the core static single-page React HTML file."""
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), status_code=200)
        return HTMLResponse(
            content="<html><body><h1>Toji React Dashboard (Missing index.html)</h1></body></html>",
            status_code=404,
        )

    @app.get("/dashboard", response_class=HTMLResponse)
    async def get_dashboard() -> HTMLResponse:
        """Redirect/serve dashboard routing to the SPA index."""
        return await get_index()

    return app


# Default app instantiation for standalone uvicorn runs (e.g. uvicorn dashboard.backend.app:app)
from dashboard.core.state import DashboardStateStore
from dashboard.core.repository import DashboardRepository
from dashboard.core.orchestrator import DashboardOrchestrator

_default_state_store = DashboardStateStore()
_default_repository = DashboardRepository()
_default_health_monitor = HealthMonitor()
_default_websocket_manager = WebSocketManager()
_default_orchestrator = DashboardOrchestrator()
_default_orchestrator.initialize(_default_state_store, _default_repository)
_default_event_aggregator = DashboardEventAggregator(
    orchestrator=_default_orchestrator,
    health_monitor=_default_health_monitor,
    websocket_manager=_default_websocket_manager,
)

app = create_app(
    state_store=_default_state_store,
    repository=_default_repository,
    health_monitor=_default_health_monitor,
    websocket_manager=_default_websocket_manager,
    event_aggregator=_default_event_aggregator,
)

