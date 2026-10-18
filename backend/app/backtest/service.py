from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
import numpy as np
import pandas as pd
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest.constants import BacktestStatus
from app.backtest.cost_model import CostModel
from app.backtest.engine import BacktestEngine, BacktestResult
from app.backtest.schemas import BacktestCreateRequest
from app.core.logging import get_logger
from app.market.service import MarketDataService
from app.models.backtest import BacktestRun, BacktestTradeLog
from app.quant.exceptions import InsufficientDataException
from app.quant.experiments.tracker import ExperimentService
from app.quant.features.pipeline import FeaturePipeline

logger = get_logger("backtest.service")


class BacktestService:
    """
    Orchestration service for managing backtest execution,
    persistence, and performance diagnostics.
    """

    def __init__(
        self,
        market_service: Optional[MarketDataService] = None,
        experiment_service: Optional[ExperimentService] = None,
        pipeline: Optional[FeaturePipeline] = None,
    ):
        self.market_service = market_service or MarketDataService()
        self.pipeline = pipeline or FeaturePipeline()
        self.experiment_service = experiment_service or ExperimentService(self.pipeline)

    async def execute_and_persist_backtest(
        self,
        db: AsyncSession,
        request: BacktestCreateRequest,
    ) -> tuple[BacktestRun, BacktestResult]:
        """
        Executes a backtest on stored validated candles and persists run records.
        """
        # 1. Fetch historical candles from database
        candles = await self.market_service.get_candles(
            db=db,
            symbol=request.symbol,
            interval=request.interval,
            start_time=request.start_time,
            end_time=request.end_time,
            limit=request.limit,
            only_closed=True,
        )

        if not candles:
            raise InsufficientDataException(
                f"No finalized candles found for {request.symbol} ({request.interval}). Please ingest market data first."
            )

        # 2. Transform into validated DataFrame
        candles_df = self.pipeline.candles_to_dataframe(candles, interval=request.interval)

        # 3. Instantiate strategy and cost model
        strategy = self.experiment_service.create_strategy_instance(
            strategy_id=request.strategy_id,
            parameters=request.parameters,
            version=request.strategy_version,
        )

        cost_model = CostModel.from_dict(request.cost_model or {})

        # 4. Execute Backtest Engine
        engine = BacktestEngine(
            cost_model=cost_model,
            pipeline=self.pipeline,
            execution_delay_bars=request.execution_delay_bars,
            initial_cash=request.initial_cash,
        )
        result = engine.run(strategy, candles_df, run_stress_tests=True)

        # 5. Persist BacktestRun Record
        run_id = str(uuid.uuid4())
        perf_dict = result.performance.to_dict()

        # Downsample equity curve if very large to prevent giant JSON payload
        eq_snapshots = result.equity_curve
        if len(eq_snapshots) > 1000:
            step = len(eq_snapshots) // 500
            serialized_equity = [s.to_dict() for s in eq_snapshots[::step]]
            serialized_equity.append(eq_snapshots[-1].to_dict())
        else:
            serialized_equity = [s.to_dict() for s in eq_snapshots]

        backtest_run = BacktestRun(
            id=run_id,
            strategy_id=result.strategy_id,
            strategy_version=result.strategy_version,
            config_id=result.config_id,
            symbol=result.symbol,
            interval=result.interval,
            time_range_start=result.time_range_start,
            time_range_end=result.time_range_end,
            candle_count=result.candle_count,
            dataset_fingerprint=result.dataset_fingerprint,
            parameters=strategy.parameters,
            cost_assumptions=result.cost_assumptions,
            status=BacktestStatus.COMPLETED.value,
            metrics=perf_dict,
            equity_curve=serialized_equity,
            total_trades=result.performance.total_trades,
            net_return_pct=result.performance.net_return_pct,
            sharpe_ratio=result.performance.sharpe_ratio,
            max_drawdown_pct=result.performance.max_drawdown_pct,
            profit_factor=round(result.performance.profit_factor, 4) if np.isfinite(result.performance.profit_factor) else None,
            win_rate_pct=result.performance.win_rate_pct,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(backtest_run)

        # 6. Persist Trade Logs
        for t in result.trades:
            trade_log = BacktestTradeLog(
                id=str(uuid.uuid4()),
                backtest_id=run_id,
                symbol=t.symbol,
                side=t.side.value if hasattr(t.side, "value") else str(t.side),
                timestamp=t.timestamp,
                fill_price=t.fill_price,
                quantity=t.quantity,
                gross_notional=t.gross_notional,
                fee=t.fee,
                slippage_cost=t.slippage_cost,
                realized_net_pnl=t.realized_net_pnl,
                created_at=datetime.now(timezone.utc),
            )
            db.add(trade_log)

        await db.commit()
        await db.refresh(backtest_run)

        logger.info(
            "backtest_run_persisted",
            run_id=run_id,
            strategy=result.strategy_id,
            net_return=result.performance.net_return_pct,
            sharpe=result.performance.sharpe_ratio,
            trades=result.performance.total_trades,
        )

        return backtest_run, result

    async def get_run(self, db: AsyncSession, run_id: str) -> Optional[BacktestRun]:
        stmt = select(BacktestRun).where(BacktestRun.id == run_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_run_trades(
        self, db: AsyncSession, run_id: str, limit: int = 500
    ) -> List[BacktestTradeLog]:
        stmt = (
            select(BacktestTradeLog)
            .where(BacktestTradeLog.backtest_id == run_id)
            .order_by(BacktestTradeLog.timestamp.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_runs(
        self,
        db: AsyncSession,
        strategy_id: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[BacktestRun]:
        stmt = select(BacktestRun)
        if strategy_id:
            stmt = stmt.where(BacktestRun.strategy_id == strategy_id)
        if symbol:
            stmt = stmt.where(BacktestRun.symbol == symbol)
        stmt = stmt.order_by(desc(BacktestRun.created_at)).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_performance_analytics(
        self,
        db: AsyncSession,
        strategy_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggregates performance analytics across recorded backtest runs."""
        runs = await self.list_runs(db, strategy_id=strategy_id, limit=100)
        if not runs:
            return {
                "strategy_id": strategy_id,
                "total_backtests": 0,
                "avg_net_return_pct": 0.0,
                "avg_sharpe_ratio": 0.0,
                "avg_max_drawdown_pct": 0.0,
                "best_net_return_pct": 0.0,
                "worst_net_return_pct": 0.0,
                "runs": [],
            }

        net_returns = [r.net_return_pct for r in runs]
        sharpes = [r.sharpe_ratio for r in runs if np.isfinite(r.sharpe_ratio)]
        drawdowns = [r.max_drawdown_pct for r in runs]

        run_summaries = [
            {
                "id": r.id,
                "strategy_id": r.strategy_id,
                "config_id": r.config_id,
                "symbol": r.symbol,
                "interval": r.interval,
                "net_return_pct": r.net_return_pct,
                "sharpe_ratio": r.sharpe_ratio,
                "max_drawdown_pct": r.max_drawdown_pct,
                "total_trades": r.total_trades,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ]

        return {
            "strategy_id": strategy_id,
            "total_backtests": len(runs),
            "avg_net_return_pct": round(float(np.mean(net_returns)), 4),
            "avg_sharpe_ratio": round(float(np.mean(sharpes)), 4) if sharpes else 0.0,
            "avg_max_drawdown_pct": round(float(np.mean(drawdowns)), 4),
            "best_net_return_pct": round(float(np.max(net_returns)), 4),
            "worst_net_return_pct": round(float(np.min(net_returns)), 4),
            "runs": run_summaries,
        }
