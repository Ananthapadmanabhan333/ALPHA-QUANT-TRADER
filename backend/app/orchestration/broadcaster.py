"""
ALPHA Quant — Phase 6: Live Broadcaster Module.
Manages WebSocket subscribers for real-time dashboard updates, reconnects, and lifecycle broadcasts.
Includes REST fallback for clients without WebSocket connectivity.
"""

import asyncio
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect

from app.core.logging import get_logger

logger = get_logger("orchestration.broadcaster")


class LiveBroadcaster:
    """
    Coordinates real-time WebSocket subscriber connections and event fanout.
    """
    def __init__(self):
        self._active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._last_event: Optional[Dict[str, Any]] = None

    @property
    def active_connection_count(self) -> int:
        return len(self._active_connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accepts connection, registers client, and dispatches initial handshake snapshot."""
        await websocket.accept()
        async with self._lock:
            self._active_connections.add(websocket)
        logger.info("websocket_client_connected", active_clients=len(self._active_connections))

        # Initial handshake snapshot
        welcome_payload = {
            "type": "SNAPSHOT",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Connected to ALPHA Quant Real-time Telemetry Feed",
            "active_subscribers": len(self._active_connections),
        }
        try:
            await websocket.send_text(json.dumps(welcome_payload))
        except Exception as exc:
            logger.warning("websocket_handshake_failed", error=str(exc))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Removes a client from active subscriber set."""
        async with self._lock:
            self._active_connections.discard(websocket)
        logger.info("websocket_client_disconnected", active_clients=len(self._active_connections))

    async def broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Dispatches structured JSON event to all connected WebSocket clients concurrently.
        Dead or stalled connections are pruned automatically.
        """
        message = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        self._last_event = message
        payload_text = json.dumps(message, default=str)

        async with self._lock:
            connections = list(self._active_connections)

        if not connections:
            return

        dead_connections: List[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(payload_text)
            except Exception as exc:
                logger.debug("websocket_send_failed", error=str(exc))
                dead_connections.append(ws)

        if dead_connections:
            async with self._lock:
                for dead_ws in dead_connections:
                    self._active_connections.discard(dead_ws)

    async def disconnect_all(self) -> None:
        """Closes all active WebSocket connections cleanly during system shutdown."""
        async with self._lock:
            connections = list(self._active_connections)
            self._active_connections.clear()

        for ws in connections:
            try:
                await ws.close(code=1001, reason="Server shutting down")
            except Exception:
                pass
        logger.info("websocket_all_clients_disconnected")

    def get_last_event(self) -> Optional[Dict[str, Any]]:
        """Provides REST fallback query for recent broadcast event."""
        return self._last_event


# Singleton instance
_broadcaster_instance: Optional[LiveBroadcaster] = None


def get_broadcaster() -> LiveBroadcaster:
    global _broadcaster_instance
    if _broadcaster_instance is None:
        _broadcaster_instance = LiveBroadcaster()
    return _broadcaster_instance
