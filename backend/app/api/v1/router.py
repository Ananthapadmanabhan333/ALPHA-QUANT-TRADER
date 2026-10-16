from fastapi import APIRouter
from app.api.v1.endpoints import (
    backtest,
    health,
    market,
    orchestration,
    paper,
    portfolio,
    strategies,
    system,
    ws,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(market.router)
api_router.include_router(strategies.router, prefix="/strategies", tags=["Quantitative Strategies"])
api_router.include_router(backtest.router, tags=["Backtesting & Analytics"])
api_router.include_router(portfolio.router, tags=["Portfolio & Execution Ledgers"])
api_router.include_router(orchestration.router, tags=["Orchestration & Lifecycle"])
api_router.include_router(paper.router, prefix="/paper", tags=["Paper Execution & Risk (Legacy Aliases)"])
api_router.include_router(ws.router, tags=["Live Updates & Telemetry"])

