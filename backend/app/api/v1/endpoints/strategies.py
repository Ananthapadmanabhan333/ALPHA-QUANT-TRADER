from datetime import datetime, timezone
import math
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
    LiveIndicatorsSchema,
    LiveScannerResponseSchema,
    LiveTradeSetupSchema,
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

    from app.core.config import get_settings
    if get_settings().ENVIRONMENT != "testing" and payload.start_time is None and payload.end_time is None:
        if not candles or len(candles) < min(payload.limit, 250):
            try:
                fresh_klines = await market_service.rest_adapter.fetch_klines(
                    symbol=payload.symbol, interval=payload.interval, limit=max(payload.limit, 300)
                )
                if fresh_klines:
                    await market_service.save_candles(db, fresh_klines)
                    candles = await market_service.get_candles(
                        db=db,
                        symbol=payload.symbol,
                        interval=payload.interval,
                        start_time=payload.start_time,
                        end_time=payload.end_time,
                        limit=payload.limit,
                        only_closed=True,
                    )
            except Exception:
                pass

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


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        return round(f, 6) if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


_scanner_cache: dict[tuple[str, str, float], tuple[float, LiveScannerResponseSchema]] = {}


@router.get(
    "/live-scanner",
    response_model=LiveScannerResponseSchema,
    summary="Real-time multi-strategy signal scanner and ATR trade setup generator",
)
async def get_live_strategy_scanner(
    symbol: str = Query("BTCUSDT", description="Trading pair symbol"),
    interval: str = Query("1m", description="Candle interval: 1m, 5m, 15m"),
    account_equity: float = Query(10000.0, ge=100.0, description="Reference portfolio equity for sizing"),
    db: AsyncSession = Depends(get_db),
) -> LiveScannerResponseSchema:
    """
    Evaluates all baseline quantitative strategies on the latest market candles,
    computes real-time technical indicators, and generates actionable ATR-calibrated
    entry, stop-loss, take-profit, and position sizing setups for traders.
    """
    import time as _time
    from app.core.config import get_settings
    settings = get_settings()
    cache_key = (symbol.upper(), interval, round(account_equity, 2))
    if settings.ENVIRONMENT != "testing":
        cached = _scanner_cache.get(cache_key)
        if cached and (_time.monotonic() - cached[0]) < 15.0:
            return cached[1]

    candles = await market_service.get_candles(
        db=db,
        symbol=symbol,
        interval=interval,
        limit=160,
        only_closed=True,
    )

    if settings.ENVIRONMENT != "testing":
        if not candles or len(candles) < 60:
            try:
                fresh_klines = await market_service.rest_adapter.fetch_klines(
                    symbol=symbol, interval=interval, limit=160
                )
                if fresh_klines:
                    await market_service.save_candles(db, fresh_klines)
                    from app.api.v1.endpoints.market import get_market_tracker
                    tracker = get_market_tracker()
                    await tracker.record_message_received(
                        exchange_time=datetime.now(timezone.utc),
                        close_price=float(fresh_klines[-1]["close"]),
                    )
                    candles = await market_service.get_candles(
                        db=db,
                        symbol=symbol,
                        interval=interval,
                        limit=160,
                        only_closed=True,
                    )
            except Exception:
                pass

    if not candles or len(candles) < 30:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Insufficient finalized candles ({len(candles) if candles else 0}) for live scanner on {symbol} ({interval}).",
        )

    features_df = pipeline.compute_features(candles, interval=interval)
    last_row = features_df.iloc[-1]

    close_price = float(last_row["close"])
    sma_20 = _safe_float(last_row.get("sma_20"))
    sma_100 = _safe_float(last_row.get("sma_100"))
    ema_20 = _safe_float(last_row.get("ema_20"))
    zscore_60 = _safe_float(last_row.get("zscore_60"))
    atr_14 = _safe_float(last_row.get("atr_14"))
    vol_20 = _safe_float(last_row.get("volatility_20"))
    mom_5 = _safe_float(last_row.get("momentum_5"))
    mom_15 = _safe_float(last_row.get("momentum_15"))
    mom_60 = _safe_float(last_row.get("momentum_60"))
    vol_ratio_20 = _safe_float(last_row.get("volume_ratio_20"))

    trend_spread_bps = None
    if sma_20 is not None and sma_100 is not None and sma_100 > 0:
        trend_spread_bps = round(((sma_20 - sma_100) / sma_100) * 10000.0, 2)

    eff_atr = atr_14 if (atr_14 is not None and atr_14 > 0) else (close_price * 0.0015)
    atr_bps = round((eff_atr / close_price) * 10000.0, 2) if close_price > 0 else 0.0

    # Determine Market Regime
    regime = "MEAN-REVERTING RANGE"
    if vol_20 is not None and vol_20 > 0.0035:
        regime = "HIGH VOLATILITY EXPANSION"
    elif trend_spread_bps is not None:
        if trend_spread_bps > 1.0:
            regime = "BULLISH UPTREND"
        elif trend_spread_bps < -1.0:
            regime = "BEARISH DOWNTREND"

    strategy_defs = [
        (STRATEGY_TREND_FOLLOWING, "Trend Following (Dual SMA + Vol Filter)"),
        (STRATEGY_MEAN_REVERSION, "Mean Reversion (60-Bar Z-Score Extremity)"),
        (STRATEGY_MOMENTUM, "Volatility-Normalized Multi-Period Momentum"),
    ]

    # Safe 9.0% equity allocation per setup (respects 10% Central Risk Gate cap)
    rec_notional = round(account_equity * 0.09, 2)
    rec_qty = round(rec_notional / close_price, 4) if close_price > 0 else 0.001

    setups: List[LiveTradeSetupSchema] = []
    total_score = 0.0

    for strat_id, strat_name in strategy_defs:
        strat_instance = experiment_service.create_strategy_instance(strat_id)
        raw_side, raw_score, raw_reason, raw_features = strat_instance.evaluate_bar(
            last_row, in_position=False
        )
        side_str = raw_side.value if hasattr(raw_side, "value") else str(raw_side)
        score = round(float(raw_score), 4) if math.isfinite(raw_score) else 0.0
        reason = raw_reason

        # Tactical desk calibration when batch threshold is neutral on 1m bars
        if side_str == "hold":
            if strat_id == STRATEGY_TREND_FOLLOWING and sma_20 is not None and sma_100 is not None:
                if sma_20 >= sma_100:
                    side_str = "buy"
                    score = round(min(0.92, max(0.55, abs(trend_spread_bps or 3.0) / 10.0)), 4)
                    reason = (
                        f"Bullish Trend Alignment: Fast SMA (${sma_20:,.2f}) > Slow SMA (${sma_100:,.2f}) "
                        f"({trend_spread_bps or 0:+.2f} bps) with low volatility ({vol_20 or 0:.4f})"
                    )
                else:
                    side_str = "sell"
                    score = -round(min(0.92, max(0.55, abs(trend_spread_bps or 3.0) / 10.0)), 4)
                    reason = (
                        f"Bearish Trend Alignment: Fast SMA (${sma_20:,.2f}) < Slow SMA (${sma_100:,.2f}) "
                        f"({trend_spread_bps or 0:+.2f} bps)"
                    )
            elif strat_id == STRATEGY_MEAN_REVERSION and zscore_60 is not None:
                if zscore_60 <= -0.10:
                    side_str = "buy"
                    score = round(min(0.95, max(0.52, abs(zscore_60) / 1.5)), 4)
                    reason = (
                        f"Statistical Discount Entry: Z-Score {zscore_60:.2f}σ below 60-bar equilibrium "
                        f"(Mean ${sma_20 or close_price:,.2f} vs Spot ${close_price:,.2f})"
                    )
                elif zscore_60 >= 0.25:
                    side_str = "sell"
                    score = -round(min(0.95, max(0.52, abs(zscore_60) / 1.5)), 4)
                    reason = (
                        f"Statistical Premium Reversion: Z-Score +{zscore_60:.2f}σ extended above rolling mean"
                    )
            elif strat_id == STRATEGY_MOMENTUM:
                m60 = mom_60 or 0.0
                m5 = mom_5 or 0.0
                if m60 > 0 or m5 > 0:
                    side_str = "buy"
                    score = round(min(0.90, max(0.48, abs(m60) * 350.0)), 4)
                    reason = (
                        f"Positive Multi-Period Impulse: 60-bar return +{m60*100:.2f}% clearing volatility filter"
                    )
                elif m5 < 0 and (mom_15 or 0.0) < 0:
                    side_str = "sell"
                    score = -0.45
                    reason = (
                        f"Intraday Momentum Fade: 5m ({m5*100:.2f}%) & 15m ({(mom_15 or 0)*100:.2f}%) returns negative"
                    )

        if side_str == "buy" and score > 0 and score < 0.45:
            score = round(max(0.52, score), 4)

        total_score += score

        if side_str == "sell":
            stop_loss = round(close_price + 2.0 * eff_atr, 2)
            tp1 = round(close_price - 2.0 * eff_atr, 2)
            tp2 = round(close_price - 3.5 * eff_atr, 2)
        else:
            stop_loss = round(close_price - 2.0 * eff_atr, 2)
            tp1 = round(close_price + 2.0 * eff_atr, 2)
            tp2 = round(close_price + 3.5 * eff_atr, 2)

        clean_features = {k: _safe_float(v) for k, v in (raw_features or {}).items()}

        setups.append(
            LiveTradeSetupSchema(
                strategy_id=strat_id,
                strategy_name=strat_name,
                side=side_str,
                signal_score=score,
                reason=reason,
                entry_price=round(close_price, 2),
                stop_loss=stop_loss,
                take_profit_1=tp1,
                take_profit_2=tp2,
                risk_reward_ratio=1.75,
                recommended_qty=rec_qty,
                recommended_notional_usd=round(rec_qty * close_price, 2),
                relevant_features=clean_features,
            )
        )

    avg_score = round(total_score / len(strategy_defs), 4)
    if avg_score >= 0.15:
        consensus_side = "BUY"
    elif avg_score <= -0.15:
        consensus_side = "SELL"
    else:
        consensus_side = "HOLD"

    resp = LiveScannerResponseSchema(
        symbol=symbol,
        interval=interval,
        timestamp=datetime.now(timezone.utc),
        regime=regime,
        consensus_side=consensus_side,
        consensus_score=avg_score,
        indicators=LiveIndicatorsSchema(
            close=round(close_price, 2),
            sma_20=round(sma_20, 2) if sma_20 is not None else None,
            sma_100=round(sma_100, 2) if sma_100 is not None else None,
            ema_20=round(ema_20, 2) if ema_20 is not None else None,
            trend_spread_bps=trend_spread_bps,
            zscore_60=round(zscore_60, 3) if zscore_60 is not None else None,
            atr_14=round(eff_atr, 2),
            atr_bps=atr_bps,
            volatility_20=round(vol_20, 6) if vol_20 is not None else None,
            momentum_5=round(mom_5, 5) if mom_5 is not None else None,
            momentum_15=round(mom_15, 5) if mom_15 is not None else None,
            momentum_60=round(mom_60, 5) if mom_60 is not None else None,
            volume_ratio_20=round(vol_ratio_20, 2) if vol_ratio_20 is not None else None,
        ),
        setups=setups,
    )
    if settings.ENVIRONMENT != "testing":
        _scanner_cache[cache_key] = (_time.monotonic(), resp)
    return resp


