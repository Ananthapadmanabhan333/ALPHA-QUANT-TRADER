"""
ALPHA Quant — Phase 6: Live Telemetry WebSocket and REST Fallback Tests.
Tests real-time WebSocket connection, snapshot handshake, ping/pong heartbeats, and REST fallback.
"""

import json
from httpx import AsyncClient
import pytest
from starlette.testclient import TestClient

from app.orchestration.broadcaster import get_broadcaster


def test_websocket_live_stream_handshake_and_ping(test_app):
    """
    Validates WebSocket /api/v1/ws/live connection:
    - Receives initial SNAPSHOT telemetry handshake.
    - Sends ping action, receives PONG response.
    """
    client = TestClient(test_app)
    with client.websocket_connect("/api/v1/ws/live") as websocket:
        # 1. First message should be the SNAPSHOT handshake
        snapshot_raw = websocket.receive_text()
        snapshot = json.loads(snapshot_raw)
        assert snapshot["type"] == "SNAPSHOT"
        assert "timestamp" in snapshot

        # 2. Send ping action
        websocket.send_text(json.dumps({"action": "ping"}))
        pong_raw = websocket.receive_text()
        pong = json.loads(pong_raw)
        assert pong["type"] == "PONG"
        assert "timestamp" in pong


@pytest.mark.asyncio
async def test_rest_fallback_endpoint(client: AsyncClient):
    """
    Validates GET /api/v1/live/fallback provides snapshot telemetry for clients
    without WebSocket connectivity.
    """
    res = await client.get("/api/v1/live/fallback?symbol=BTCUSDT")
    assert res.status_code == 200
    data = res.json()
    assert "orchestrator" in data
    assert "portfolio" in data
    assert "risk" in data
    assert "timestamp" in data
    assert "virtual_balance" in data["portfolio"]
    assert "is_trading_allowed" in data["risk"]
