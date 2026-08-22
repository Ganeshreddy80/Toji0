"""WebSocket Manager for thread-safe websocket connections and channel broadcasts."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Dict, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages active WebSocket connections grouped by update channels."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        
        # Channel -> WebSockets list
        self._connections: Dict[str, List[WebSocket]] = {
            "market": [],
            "patterns": [],
            "confluence": [],
            "strategy": [],
            "risk": [],
            "position": [],
            "system": [],
            "logs": [],
        }
        
        # Event loop reference for sync-to-async bridging
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        """Accept connection and add it to the channel updates list."""
        await websocket.accept()
        
        # Capture the event loop running uvicorn
        if not self._loop:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

        with self._lock:
            normalized_channel = channel.lower()
            if normalized_channel not in self._connections:
                self._connections[normalized_channel] = []
            self._connections[normalized_channel].append(websocket)
            logger.debug("WebSocket: Client connected to channel '%s'.", normalized_channel)

    def disconnect(self, websocket: WebSocket, channel: str) -> None:
        """Remove a disconnected client from the channel list."""
        with self._lock:
            normalized_channel = channel.lower()
            if (
                normalized_channel in self._connections
                and websocket in self._connections[normalized_channel]
            ):
                self._connections[normalized_channel].remove(websocket)
                logger.debug("WebSocket: Client disconnected from channel '%s'.", normalized_channel)

    def broadcast(self, channel: str, message: Any) -> None:
        """Thread-safe broadcast method that delegates async calls using run_coroutine_threadsafe."""
        # Clean channel key
        normalized_channel = channel.lower()
        
        # Check if uvicorn loop is active
        if self._loop and self._loop.is_running():
            coro = self._async_broadcast(normalized_channel, message)
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        else:
            # Fallback if loop is not running yet (e.g. in test assertions)
            # Create a new temporary task or run synchronously if in loop
            try:
                current_loop = asyncio.get_running_loop()
                if current_loop.is_running():
                    current_loop.create_task(self._async_broadcast(normalized_channel, message))
            except RuntimeError:
                pass

    async def _async_broadcast(self, channel: str, message: Any) -> None:
        """Asynchronously send JSON message to all clients subscribed to a channel."""
        with self._lock:
            websockets = list(self._connections.get(channel, []))

        for ws in websockets:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.debug("WebSocket: Broadcast failed for a client, disconnecting: %s", e)
                self.disconnect(ws, channel)
