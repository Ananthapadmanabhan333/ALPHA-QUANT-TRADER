from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.market.service import MarketDataService
from app.quant.constants import (
    DEFAULT_MEAN_REVERSION_PARAMS,
    DEFAULT_MOMENTUM_PARAMS,
    DEFAULT_TREND_FOLLOWING_PARAMS,
    STRATEGY_MEAN_REVERSION,
    STRATEGY_MOMENTUM,
    STRATEGY_TREND_FOLLOWING,
    SUPPORTED_STRATEGIES,
)
from app.quant.exceptions import (
    InsufficientDataException,
    QuantException,
)
from app.quant.experiments.tracker import ExperimentService
from app.quant.features.pipeline import FeaturePipeline
from app.quant.schemas import (
    ExperimentListResponse,
    ExperimentResponseSchema,
    RunStrategyRequest,
    SignalResponseSchema,
    StrategyInfoSchema,
)

router = APIRouter()
market_service = MarketDataService()
experiment_service = ExperimentService()
pipeline = FeaturePipeline()


@router.get(
    "",
    response_model=List[StrategyInfoSchema],
    summary="List available baseline quantitative strategies",
)
async def list_available_strategies():
    """
    Returns registered baseline strategies, their descriptions, candidate parameters,
    and required feature pipeline inputs.
    """
    return [
        StrategyInfoSchema(
            strategy_id=STRATEGY_TREND_FOLLOWING,
            name="Trend Following (Dual Moving Average + Volatility Filter)",
            version="1.0.0",
            description="Dual SMA crossover with rolling return volatility regime filter and explicit trend exit conditions.",
            candidate_parameters=DEFAULT_TREND_FOLLOWING_PARAMS,
            features_used=["sma_20", "sma_100", "volatility_20"],
        ),
        StrategyInfoSchema(
            strategy_id=STRATEGY_MEAN_REVERSION,
            name="Mean Reversion (Rolling Z-Score + Regime Filter)",
            version="1.0.0",
            description="Statistical mean reversion on 60-bar rolling z-score with trend regime filter and explicit exit conditions.",
            candidate_parameters=DEFAULT_MEAN_REVERSION_PARAMS,
            features_used=["zscore_60", "sma_100", "close"],
        ),
        StrategyInfoSchema(
            strategy_id=STRATEGY_MOMENTUM,
            name="Momentum (Volatility-Normalized Multi-Period)",
            version="1.0.0",
            description="Multi-period momentum returns normalized by volatility with transaction cost hurdle verification.",
            candidate_parameters=DEFAULT_MOMENTUM_PARAMS,
            features_used=["momentum_5", "momentum_15", "momentum_60", "volatility_20"],
        ),
    ]


@router.post(
    "/run",
    response_model=ExperimentResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Execute strategy experiment on validated historical candles",
)
async def run_strategy_experiment(
    payload: RunStrategyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Executes a strategy against validated stored candles, calculates features,
    generates deterministic signals, records cryptographic dataset fingerprint,
    and persists an auditable experiment without executing live orders.
    """
    if payload.strategy_id not in SUPPORTED_STRATEGIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported strategy '{payload.strategy_id}'. Supported: {SUPPORTED_STRATEGIES}",
        )

    # 1. Fetch validated finalized candles from storage
    candles = await market_service.get_candles(
        db=db,
        symbol=payload.symbol,
        interval=payload.interval,
        start_time=payload.start_time,
        end_time=payload.end_time,
        limit=payload.limit,
        only_closed=True,
    )

    if not candles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No finalized candles found for {payload.symbol} ({payload.interval}). Please ingest market data first.",
        )

    # 2. Transform into validated DataFrame
    try:
        candles_df = pipeline.candles_to_dataframe(candles, interval=payload.interval)
        experiment, signals = await experiment_service.execute_and_persist_experiment(
            db=db,
            strategy_id=payload.strategy_id,
            candles_df=candles_df,
            parameters=payload.parameters,
        )
    except InsufficientDataException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient candle history: {str(exc)}",
        )
    except QuantException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    signal_responses = [
        SignalResponseSchema(
            strategy_id=s.strategy_id,
            strategy_version=s.strategy_version,
            decision_timestamp=s.decision_timestamp,
            symbol=s.symbol,
            side=s.side.value if hasattr(s.side, "value") else str(s.side),
            signal_score=s.signal_score,
            reference_price=s.reference_price,
            reason=s.reason,
            relevant_features=s.relevant_features,
            config_id=s.config_id,
        )
        for s in signals
    ]

    return ExperimentResponseSchema(
        id=experiment.id,
        strategy_id=experiment.strategy_id,
        strategy_version=experiment.strategy_version,
        config_id=experiment.config_id,
        symbol=experiment.symbol,
        interval=experiment.interval,
        time_range_start=experiment.time_range_start,
        time_range_end=experiment.time_range_end,
        candle_count=experiment.candle_count,
        dataset_fingerprint=experiment.dataset_fingerprint,
        parameters=experiment.parameters,
        total_signals=experiment.total_signals,
        buy_signals=experiment.buy_signals,
        sell_signals=experiment.sell_signals,
        hold_signals=experiment.hold_signals,
        created_at=experiment.created_at,
        signals=signal_responses,
    )


@router.get(
    "/experiments",
    response_model=ExperimentListResponse,
    summary="List historical strategy experiments",
)
async def list_experiments(
    strategy_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    experiments = await experiment_service.list_experiments(
        db=db,
        strategy_id=strategy_id,
        symbol=symbol,
        limit=limit,
    )
    items = [
        ExperimentResponseSchema(
            id=exp.id,
            strategy_id=exp.strategy_id,
            strategy_version=exp.strategy_version,
            config_id=exp.config_id,
            symbol=exp.symbol,
            interval=exp.interval,
            time_range_start=exp.time_range_start,
            time_range_end=exp.time_range_end,
            candle_count=exp.candle_count,
            dataset_fingerprint=exp.dataset_fingerprint,
            parameters=exp.parameters,
            total_signals=exp.total_signals,
            buy_signals=exp.buy_signals,
            sell_signals=exp.sell_signals,
            hold_signals=exp.hold_signals,
            created_at=exp.created_at,
        )
        for exp in experiments
    ]
    return ExperimentListResponse(count=len(items), experiments=items)


@router.get(
    "/experiments/{experiment_id}",
    response_model=ExperimentResponseSchema,
    summary="Get experiment details and its signals",
)
async def get_experiment_details(
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
):
    experiment = await experiment_service.get_experiment(db, experiment_id)
    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found.",
        )

    db_signals = await experiment_service.get_experiment_signals(db, experiment_id)
    signals = [
        SignalResponseSchema(
            strategy_id=s.strategy_id,
            strategy_version=s.strategy_version,
            decision_timestamp=s.decision_timestamp,
            symbol=s.symbol,
            side=s.side,
            signal_score=s.signal_score,
            reference_price=s.reference_price,
            reason=s.reason,
            relevant_features=s.relevant_features,
            config_id=s.config_id,
        )
        for s in db_signals
    ]

    return ExperimentResponseSchema(
        id=experiment.id,
        strategy_id=experiment.strategy_id,
        strategy_version=experiment.strategy_version,
        config_id=experiment.config_id,
        symbol=experiment.symbol,
        interval=experiment.interval,
        time_range_start=experiment.time_range_start,
        time_range_end=experiment.time_range_end,
        candle_count=experiment.candle_count,
        dataset_fingerprint=experiment.dataset_fingerprint,
        parameters=experiment.parameters,
        total_signals=experiment.total_signals,
        buy_signals=experiment.buy_signals,
        sell_signals=experiment.sell_signals,
        hold_signals=experiment.hold_signals,
        created_at=experiment.created_at,
        signals=signals,
    )
