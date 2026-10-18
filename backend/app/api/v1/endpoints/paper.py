"""
FastAPI REST endpoints for ALPHA Quant Phase 5 Paper Execution & Risk Subsystem.
Provides simulated order submission, portfolio reconciliation, risk telemetry, and emergency controls.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_key
from app.db.session import get_db
from app.paper.exceptions import (
    DuplicateOrderException,
    EmergencyStopActiveException,
    InsufficientBalanceException,
    InvalidOrderException,
    LiveTradingForbiddenException,
    OrderNotFoundException,
    PaperExecutionException,
    ReconciliationException,
    RiskBreachException,
    StaleFeedException,
)
from app.paper.schemas import (
    EmergencyResumeRequest,
    EmergencyStopRequest,
    MarketPriceUpdateRequest,
    PaperAccountResetRequest,
    PaperAccountResponse,
    PaperFillResponse,
    PaperOrderCreateRequest,
    PaperOrderResponse,
    PaperPositionResponse,
    RiskStatusResponse,
)
from app.paper.service import PaperService

router = APIRouter()
paper_service = PaperService()


@router.get(
    "/account",
    response_model=PaperAccountResponse,
    summary="Get simulated paper account overview",
)
async def get_paper_account(
    symbol: str = Query("BTCUSDT", description="Symbol for mark price valuation"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns virtual cash balance, positions, cost basis, and realized/unrealized P&L.
    """
    try:
        return await paper_service.get_account_overview(db, symbol=symbol)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/account/reset",
    response_model=PaperAccountResponse,
    summary="Reset simulated paper account capital and positions",
)
async def reset_paper_account(
    payload: PaperAccountResetRequest,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(verify_admin_key),
):
    """
    Resets the virtual paper account to a clean starting USDT capital (e.g. $10,000, $50,000, $100,000)
    so a trader can start a fresh session or adjust virtual capital allocation.
    """
    try:
        return await paper_service.reset_paper_account(
            db=db,
            initial_cash=payload.initial_cash,
            clear_history=payload.clear_history,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))



@router.post(
    "/orders",
    response_model=PaperOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit simulated paper order",
)
async def submit_paper_order(
    payload: PaperOrderCreateRequest,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(verify_admin_key),
):
    """
    Submits a simulated market or limit order.
    Safety Invariants:
    1. Strictly evaluated by Central Risk Gate.
    2. Zero live exchange orders or credentials.
    3. Idempotent submission via client_order_id.
    """
    try:
        return await paper_service.submit_paper_order(db=db, request=payload)
    except LiveTradingForbiddenException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except EmergencyStopActiveException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except StaleFeedException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RiskBreachException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "RISK_BREACH", "rule": exc.rule_name, "message": str(exc), "details": exc.details},
        )
    except InsufficientBalanceException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except InvalidOrderException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except DuplicateOrderException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except PaperExecutionException as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get(
    "/orders",
    response_model=List[PaperOrderResponse],
    summary="List simulated paper orders",
)
async def list_paper_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await paper_service.list_orders(db=db, status=status_filter, symbol=symbol, limit=limit)


@router.get(
    "/orders/{order_id}",
    response_model=dict,
    summary="Get simulated order details and execution fills",
)
async def get_paper_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        order, fills = await paper_service.get_order_details(db, order_id)
        return {"order": order, "fills": fills}
    except OrderNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/orders/{order_id}",
    response_model=PaperOrderResponse,
    summary="Cancel open paper limit order",
)
async def cancel_paper_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(verify_admin_key),
):
    try:
        return await paper_service.cancel_paper_order(db, order_id)
    except OrderNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/positions",
    response_model=List[PaperPositionResponse],
    summary="List open simulated spot positions",
)
async def list_paper_positions(
    symbol: str = Query("BTCUSDT"),
    db: AsyncSession = Depends(get_db),
):
    overview = await paper_service.get_account_overview(db, symbol=symbol)
    return overview.positions


@router.get(
    "/risk/status",
    response_model=RiskStatusResponse,
    summary="Get Central Risk Gate telemetry and limits",
)
async def get_risk_status(
    symbol: str = Query("BTCUSDT"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns live risk parameters, current daily PnL, drawdown %, streak losses, and kill-switch status.
    """
    return await paper_service.get_risk_status(db, symbol=symbol)


@router.post(
    "/risk/emergency-stop",
    response_model=RiskStatusResponse,
    summary="Trigger Emergency Stop / Kill Switch",
)
async def trigger_emergency_stop(
    payload: EmergencyStopRequest,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(verify_admin_key),
):
    """
    Halts all simulated entry orders immediately. Persists critical risk event.
    """
    return await paper_service.trigger_emergency_stop(db, reason=payload.reason)


@router.post(
    "/risk/resume",
    response_model=RiskStatusResponse,
    summary="Resume trading from Emergency Stop",
)
async def resume_emergency_stop(
    payload: EmergencyResumeRequest,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(verify_admin_key),
):
    """
    Clears emergency pause following explicit confirmation token 'CONFIRM_RESUME'.
    """
    try:
        return await paper_service.resume_emergency_stop(
            db,
            confirmation=payload.confirmation,
            reset_consecutive_losses=payload.reset_consecutive_losses,
        )
    except InvalidOrderException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/match-market",
    response_model=List[PaperFillResponse],
    summary="Simulate market price tick / candle matching",
)
async def match_market_price(
    payload: MarketPriceUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Feeds market price tick to evaluate and fill pending open limit orders.
    """
    return await paper_service.match_market_price(
        db=db,
        symbol=payload.symbol,
        price=payload.price,
        high=payload.high,
        low=payload.low,
        volume=payload.volume,
    )
