from typing import Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest.schemas import (
    BacktestCreateRequest,
    BacktestListResponse,
    BacktestRunResponse,
    EquitySnapshotSchema,
    PerformanceAnalyticsResponse,
    TradeResponseSchema,
)
from app.backtest.service import BacktestService
from app.core.security import verify_admin_key
from app.db.session import get_db, get_session_factory
from app.orchestration.tasks import get_task_manager
from app.quant.constants import SUPPORTED_STRATEGIES
from app.quant.exceptions import InsufficientDataException, QuantException
from app.schemas.orchestration import AsyncTaskResponse

router = APIRouter()
backtest_service = BacktestService()


@router.post(
    "/backtests",
    response_model=Union[BacktestRunResponse, AsyncTaskResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Execute and persist event-driven backtest simulation",
)
async def create_backtest_run(
    payload: BacktestCreateRequest,
    response: Response,
    async_mode: bool = Query(False, description="Execute asynchronously in background worker"),
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(verify_admin_key),
):
    """
    Executes a deterministic event-driven backtest over historical candles.
    Simulates next-bar execution, fees, adverse slippage, and liquidity constraints.
    Persists auditable run metrics and trade log.
    """
    if payload.strategy_id not in SUPPORTED_STRATEGIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported strategy '{payload.strategy_id}'. Supported: {SUPPORTED_STRATEGIES}",
        )

    if async_mode:
        task_manager = get_task_manager()
        session_factory = get_session_factory()

        async def _run_async_backtest():
            async with session_factory() as async_session:
                run_rec, res = await backtest_service.execute_and_persist_backtest(
                    db=async_session,
                    request=payload,
                )
                return {
                    "run_id": run_rec.id,
                    "strategy_id": run_rec.strategy_id,
                    "net_return_pct": run_rec.net_return_pct,
                    "sharpe_ratio": run_rec.sharpe_ratio,
                    "total_trades": run_rec.total_trades,
                }

        task_record = task_manager.enqueue_task(
            task_type="BACKTEST_SIMULATION",
            coro_fn=_run_async_backtest,
            metadata={"strategy_id": payload.strategy_id, "symbol": payload.symbol},
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return AsyncTaskResponse(**task_record.to_dict())

    try:
        run_record, result = await backtest_service.execute_and_persist_backtest(
            db=db,
            request=payload,
        )
    except InsufficientDataException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except QuantException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # Serialize snapshots and trade records
    trades_resp = [
        TradeResponseSchema(
            trade_id=t.trade_id,
            order_id=t.order_id,
            timestamp=t.timestamp,
            symbol=t.symbol,
            side=t.side.value if hasattr(t.side, "value") else str(t.side),
            fill_price=t.fill_price,
            quantity=t.quantity,
            gross_notional=t.gross_notional,
            fee=t.fee,
            slippage_cost=t.slippage_cost,
            realized_gross_pnl=t.realized_gross_pnl,
            realized_net_pnl=t.realized_net_pnl,
        )
        for t in result.trades
    ]

    equity_resp = [
        EquitySnapshotSchema(
            timestamp=s.timestamp,
            cash=s.cash,
            positions_value=s.positions_value,
            total_equity=s.total_equity,
            gross_pnl=s.gross_pnl,
            net_pnl=s.net_pnl,
            cumulative_fees=s.cumulative_fees,
            cumulative_slippage=s.cumulative_slippage,
            drawdown_pct=s.drawdown_pct,
            in_position=s.in_position,
        )
        for s in result.equity_curve
    ]

    return BacktestRunResponse(
        id=run_record.id,
        strategy_id=run_record.strategy_id,
        strategy_version=run_record.strategy_version,
        config_id=run_record.config_id,
        symbol=run_record.symbol,
        interval=run_record.interval,
        time_range_start=run_record.time_range_start,
        time_range_end=run_record.time_range_end,
        candle_count=run_record.candle_count,
        dataset_fingerprint=run_record.dataset_fingerprint,
        parameters=run_record.parameters,
        cost_assumptions=run_record.cost_assumptions,
        status=run_record.status,
        metrics=run_record.metrics,
        total_trades=run_record.total_trades,
        net_return_pct=run_record.net_return_pct,
        sharpe_ratio=run_record.sharpe_ratio,
        max_drawdown_pct=run_record.max_drawdown_pct,
        profit_factor=run_record.profit_factor,
        win_rate_pct=run_record.win_rate_pct,
        created_at=run_record.created_at,
        completed_at=run_record.completed_at,
        equity_curve=equity_resp,
        trades=trades_resp,
        regime_performance=result.regime_performance,
        stress_test_results=result.stress_test_results,
    )


@router.get(
    "/backtests",
    response_model=BacktestListResponse,
    summary="List historical backtest runs",
)
async def list_backtest_runs(
    strategy_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    runs = await backtest_service.list_runs(
        db=db,
        strategy_id=strategy_id,
        symbol=symbol,
        limit=limit,
    )
    items = [
        BacktestRunResponse(
            id=r.id,
            strategy_id=r.strategy_id,
            strategy_version=r.strategy_version,
            config_id=r.config_id,
            symbol=r.symbol,
            interval=r.interval,
            time_range_start=r.time_range_start,
            time_range_end=r.time_range_end,
            candle_count=r.candle_count,
            dataset_fingerprint=r.dataset_fingerprint,
            parameters=r.parameters,
            cost_assumptions=r.cost_assumptions,
            status=r.status,
            metrics=r.metrics,
            total_trades=r.total_trades,
            net_return_pct=r.net_return_pct,
            sharpe_ratio=r.sharpe_ratio,
            max_drawdown_pct=r.max_drawdown_pct,
            profit_factor=r.profit_factor,
            win_rate_pct=r.win_rate_pct,
            created_at=r.created_at,
            completed_at=r.completed_at,
        )
        for r in runs
    ]
    return BacktestListResponse(count=len(items), backtests=items)


@router.get(
    "/backtests/{run_id}",
    response_model=BacktestRunResponse,
    summary="Get details of a specific backtest run",
)
async def get_backtest_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    run_record = await backtest_service.get_run(db, run_id)
    if not run_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest run '{run_id}' not found.",
        )

    trades = await backtest_service.get_run_trades(db, run_id)
    trades_resp = [
        TradeResponseSchema(
            trade_id=t.id,
            order_id=t.id,
            timestamp=t.timestamp,
            symbol=t.symbol,
            side=t.side,
            fill_price=t.fill_price,
            quantity=t.quantity,
            gross_notional=t.gross_notional,
            fee=t.fee,
            slippage_cost=t.slippage_cost,
            realized_gross_pnl=t.realized_net_pnl + t.fee + t.slippage_cost,
            realized_net_pnl=t.realized_net_pnl,
        )
        for t in trades
    ]

    # Parse serialized equity curve
    equity_resp = [
        EquitySnapshotSchema(
            timestamp=s["timestamp"],
            cash=s["cash"],
            positions_value=s["positions_value"],
            total_equity=s["total_equity"],
            gross_pnl=s["gross_pnl"],
            net_pnl=s["net_pnl"],
            cumulative_fees=s["cumulative_fees"],
            cumulative_slippage=s["cumulative_slippage"],
            drawdown_pct=s["drawdown_pct"],
            in_position=s["in_position"],
        )
        for s in run_record.equity_curve
    ]

    metrics_dict = run_record.metrics or {}
    return BacktestRunResponse(
        id=run_record.id,
        strategy_id=run_record.strategy_id,
        strategy_version=run_record.strategy_version,
        config_id=run_record.config_id,
        symbol=run_record.symbol,
        interval=run_record.interval,
        time_range_start=run_record.time_range_start,
        time_range_end=run_record.time_range_end,
        candle_count=run_record.candle_count,
        dataset_fingerprint=run_record.dataset_fingerprint,
        parameters=run_record.parameters,
        cost_assumptions=run_record.cost_assumptions,
        status=run_record.status,
        metrics=metrics_dict,
        total_trades=run_record.total_trades,
        net_return_pct=run_record.net_return_pct,
        sharpe_ratio=run_record.sharpe_ratio,
        max_drawdown_pct=run_record.max_drawdown_pct,
        profit_factor=run_record.profit_factor,
        win_rate_pct=run_record.win_rate_pct,
        created_at=run_record.created_at,
        completed_at=run_record.completed_at,
        equity_curve=equity_resp,
        trades=trades_resp,
        regime_performance=metrics_dict.get("regime_performance"),
        stress_test_results=metrics_dict.get("stress_test_results"),
    )


@router.get(
    "/analytics/performance",
    response_model=PerformanceAnalyticsResponse,
    summary="Get aggregated performance metrics across backtests",
)
async def get_performance_analytics(
    strategy_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    data = await backtest_service.get_performance_analytics(db, strategy_id=strategy_id)
    return PerformanceAnalyticsResponse(**data)
