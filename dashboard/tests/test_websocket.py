import asyncio
import pytest
from unittest.mock import AsyncMock
from dashboard.websocket.websocket_manager import WebSocketManager


class MockWebSocket:
    """Mock implementation of FastAPI WebSocket client."""

    def __init__(self) -> None:
        self.accept = AsyncMock()
        self.send_json = AsyncMock()
        self.close = AsyncMock()


def test_websocket_manager_connect_disconnect() -> None:
    """Test connecting and disconnecting clients from target channels."""
    async def run_test() -> None:
        manager = WebSocketManager()
        ws = MockWebSocket()

        # Connect client
        await manager.connect(ws, "market")
        ws.accept.assert_called_once()
        assert ws in manager._connections["market"]

        # Disconnect client
        manager.disconnect(ws, "market")
        assert ws not in manager._connections["market"]
    
    asyncio.run(run_test())


def test_websocket_manager_broadcast() -> None:
    """Test broadcasting to subscribed clients using Mock WebSockets."""
    async def run_test() -> None:
        manager = WebSocketManager()
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        # Connect both to system channel
        await manager.connect(ws1, "system")
        await manager.connect(ws2, "system")

        # Mock the loop to simulate uvicorn loop running
        loop = asyncio.get_running_loop()
        manager._loop = loop

        # Broadcast message
        message = {"status": "update"}
        manager.broadcast("system", message)

        # Let loop process background tasks
        await asyncio.sleep(0.05)

        ws1.send_json.assert_called_once_with(message)
        ws2.send_json.assert_called_once_with(message)

    asyncio.run(run_test())


def test_websocket_manager_broadcast_error_disconnect() -> None:
    """Test that a failed send_json automatically disconnects the client."""
    async def run_test() -> None:
        manager = WebSocketManager()
        ws = MockWebSocket()
        ws.send_json.side_effect = RuntimeError("Broken pipe")

        await manager.connect(ws, "logs")
        
        # Trigger broadcast directly
        await manager._async_broadcast("logs", {"msg": "test"})
        
        # Assert client has been cleaned up due to exception
        assert ws not in manager._connections["logs"]

    asyncio.run(run_test())

