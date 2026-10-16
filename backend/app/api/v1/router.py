from fastapi import APIRouter
from app.api.v1.endpoints import health, system, market, strategies, backtest

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(market.router)
api_router.include_router(strategies.router, prefix="/strategies", tags=["Quantitative Strategies"])
api_router.include_router(backtest.router, tags=["Backtesting & Analytics"])
