"""
ALPHA Quant — Phase 6: Live Updates WebSocket & REST Fallback Endpoints.
Provides real-time telemetry streaming for portfolio metrics, risk events, and orchestrator cycles.
Includes automatic handshake snapshots, ping/pong keepalives, and a REST fallback endpoint.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.orchestration.broadcaster import get_broadcaster
from app.orchestration.lifecycle import get_lifecycle_manager
from app.paper.service import PaperService

router = APIRouter()
broadcaster = get_broadcaster()
paper_service = PaperService()


@router.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard telemetry updates.
    On connection:
    - Delivers current snapshot (orchestration status, portfolio equity, risk status).
    - Streams subsequent TICK, ORCHESTRATOR_CYCLE, ORDER_UPDATE, and RISK_ALERT events.
    - Handles heartbeat ping/pong messages from clients.
    """
    await broadcaster.connect(websocket)
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
                action = data.get("action", "").lower()
                if action == "ping":
                    pong_response = {
                        "type": "PONG",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    await websocket.send_text(json.dumps(pong_response))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)
    except Exception:
        await broadcaster.disconnect(websocket)


@router.get(
    "/live/fallback",
    summary="REST fallback for live updates snapshot",
)
async def get_live_fallback(
    symbol: str = Query("BTCUSDT"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    REST fallback endpoint for clients unable to maintain persistent WebSocket connections.
    Returns orchestrator state, portfolio equity, and recent broadcast event.
    """
    manager = get_lifecycle_manager()
    overview = await paper_service.get_account_overview(db, symbol=symbol)
    risk_status = await paper_service.get_risk_status(db, symbol=symbol)
    last_event = broadcaster.get_last_event()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "orchestrator": manager.get_status(),
        "portfolio": {
            "virtual_balance": overview.virtual_balance,
            "total_equity": overview.total_equity,
            "cash": overview.virtual_balance,
            "positions_count": len(overview.positions),
        },
        "risk": {
            "emergency_stop": risk_status.emergency_stop,
            "is_trading_allowed": risk_status.is_trading_allowed,
            "current_drawdown_pct": risk_status.current_drawdown_pct,
            "daily_loss_pct": round((abs(risk_status.current_daily_pnl) / risk_status.total_equity) * 100, 2)
            if risk_status.current_daily_pnl < 0
            else 0.0,
        },
        "last_broadcast_event": last_event,
    }
