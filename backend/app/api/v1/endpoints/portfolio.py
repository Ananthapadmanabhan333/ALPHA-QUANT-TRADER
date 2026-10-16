"""
ALPHA Quant — Phase 6: Unified Portfolio & Execution Read Endpoints.
Provides institutional portfolio summaries, paginated orders and fills ledgers, and Central Risk Gate status.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.paper.schemas import (
    PaperAccountResponse,
    PaperFillResponse,
    PaperOrderResponse,
    RiskStatusResponse,
)
from app.paper.service import PaperService
from app.schemas.pagination import PaginatedResponse

router = APIRouter()
paper_service = PaperService()


@router.get(
    "/portfolio",
    response_model=PaperAccountResponse,
    summary="Get simulated portfolio overview and active positions",
)
async def get_portfolio_overview(
    symbol: str = Query("BTCUSDT", description="Symbol for mark price valuation"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns virtual cash balance, positions, cost basis, exposure %, and realized/unrealized P&L.
    """
    try:
        return await paper_service.get_account_overview(db, symbol=symbol)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/orders",
    response_model=PaginatedResponse[PaperOrderResponse],
    summary="List simulated paper orders with pagination and filtering",
)
async def list_orders(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by order status"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    side: Optional[str] = Query(None, description="Filter by side: buy, sell"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns paginated list of historical and resting simulated orders.
    """
    total, items = await paper_service.list_orders_paginated(
        db=db,
        status=status_filter,
        symbol=symbol,
        side=side,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get(
    "/fills",
    response_model=PaginatedResponse[PaperFillResponse],
    summary="List simulated execution fills with pagination and filtering",
)
async def list_fills(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    side: Optional[str] = Query(None, description="Filter by side: buy, sell"),
    order_id: Optional[str] = Query(None, description="Filter by parent order ID"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns paginated execution audit records with fill prices, slippage, and transaction fees.
    """
    total, items = await paper_service.list_fills_paginated(
        db=db,
        symbol=symbol,
        side=side,
        order_id=order_id,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get(
    "/risk/status",
    response_model=RiskStatusResponse,
    summary="Get Central Risk Gate telemetry, thresholds, and kill-switch status",
)
async def get_risk_status(
    symbol: str = Query("BTCUSDT", description="Symbol for feed freshness evaluation"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns live pre-trade risk controls, peak-to-trough drawdown, daily loss limit, and emergency stop state.
    """
    return await paper_service.get_risk_status(db, symbol=symbol)
