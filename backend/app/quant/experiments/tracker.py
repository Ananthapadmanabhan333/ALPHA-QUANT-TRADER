from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional
import uuid
import pandas as pd
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.strategy import StrategyExperiment, StrategySignal
from app.quant.constants import (
    STRATEGY_MEAN_REVERSION,
    STRATEGY_MOMENTUM,
    STRATEGY_TREND_FOLLOWING,
    SignalSide,
)
from app.quant.exceptions import (
    InsufficientDataException,
    QuantException,
)
from app.quant.features.pipeline import FeaturePipeline
from app.quant.strategy.base import BaseStrategy, Signal
from app.quant.strategy.mean_reversion import MeanReversionStrategy
from app.quant.strategy.momentum import MomentumStrategy
from app.quant.strategy.trend_following import TrendFollowingStrategy

logger = get_logger("quant.experiments")


def compute_dataset_fingerprint(df: pd.DataFrame) -> str:
    """
    Computes a cryptographic SHA-256 fingerprint of the input dataset.
    Hashes symbol, interval, length, time boundaries, and exact price/volume sequence.
    """
    if df.empty:
        return hashlib.sha256(b"empty_dataset").hexdigest()

    symbol = str(df["symbol"].iloc[0]) if "symbol" in df.columns else "UNKNOWN"
    interval = str(df["interval"].iloc[0]) if "interval" in df.columns else "1m"
    count = len(df)
    first_time = str(df["open_time"].iloc[0])
    last_time = str(df["open_time"].iloc[-1])

    header = f"{symbol}:{interval}:{count}:{first_time}:{last_time}"
    hasher = hashlib.sha256(header.encode("utf-8"))

    # Hash rows deterministically
    for _, row in df.iterrows():
        row_str = f"{row['open_time']}:{row['open']:.8f}:{row['high']:.8f}:{row['low']:.8f}:{row['close']:.8f}:{row['volume']:.8f}"
        hasher.update(row_str.encode("utf-8"))

    return hasher.hexdigest()


class ExperimentService:
    """
    Service for executing strategies, recording auditable experiments,
    and persisting deterministic signals without order execution.
    """

    def __init__(self, pipeline: Optional[FeaturePipeline] = None):
        self.pipeline = pipeline or FeaturePipeline()

    def create_strategy_instance(
        self,
        strategy_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0",
    ) -> BaseStrategy:
        """Factory method for instantiating baseline strategies."""
        if strategy_id == STRATEGY_TREND_FOLLOWING:
            return TrendFollowingStrategy(parameters=parameters, version=version)
        elif strategy_id == STRATEGY_MEAN_REVERSION:
            return MeanReversionStrategy(parameters=parameters, version=version)
        elif strategy_id == STRATEGY_MOMENTUM:
            return MomentumStrategy(parameters=parameters, version=version)
        else:
            raise QuantException(f"Unsupported strategy '{strategy_id}'")

    def run_strategy_on_dataframe(
        self,
        strategy: BaseStrategy,
        df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, List[Signal], str, Dict[str, Any]]:
        """
        Executes feature pipeline and strategy on input DataFrame.
        Returns: (features_df, signals, dataset_fingerprint, feature_docs)
        """
        if df.empty:
            raise InsufficientDataException("Cannot run experiment on empty dataset.")

        fingerprint = compute_dataset_fingerprint(df)
        features_df = self.pipeline.compute_all_features(df)
        feature_docs = self.pipeline.get_feature_documentation()
        signals = strategy.generate_signals(features_df)

        return features_df, signals, fingerprint, feature_docs

    async def execute_and_persist_experiment(
        self,
        db: AsyncSession,
        strategy_id: str,
        candles_df: pd.DataFrame,
        parameters: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0",
        experiment_id: Optional[str] = None,
    ) -> tuple[StrategyExperiment, List[Signal]]:
        """
        Executes strategy and transactionally persists experiment record and all signals.
        """
        strategy = self.create_strategy_instance(strategy_id, parameters, version)
        features_df, signals, fingerprint, feature_docs = self.run_strategy_on_dataframe(
            strategy, candles_df
        )

        exp_id = experiment_id or str(uuid.uuid4())
        symbol = str(candles_df["symbol"].iloc[0]) if "symbol" in candles_df.columns else "BTCUSDT"
        interval = str(candles_df["interval"].iloc[0]) if "interval" in candles_df.columns else "1m"

        start_dt = candles_df["open_time"].iloc[0]
        end_dt = candles_df["open_time"].iloc[-1]
        if isinstance(start_dt, pd.Timestamp):
            start_dt = start_dt.to_pydatetime()
        if isinstance(end_dt, pd.Timestamp):
            end_dt = end_dt.to_pydatetime()
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)

        # Summarize signal sides
        total_signals = len(signals)
        buy_signals = sum(1 for s in signals if s.side == SignalSide.BUY)
        sell_signals = sum(1 for s in signals if s.side == SignalSide.SELL)
        hold_signals = sum(1 for s in signals if s.side == SignalSide.HOLD)
        signal_timestamps = [s.decision_timestamp.isoformat() for s in signals]

        experiment = StrategyExperiment(
            id=exp_id,
            strategy_id=strategy.strategy_id,
            strategy_version=strategy.version,
            config_id=strategy.config_id,
            symbol=symbol,
            interval=interval,
            time_range_start=start_dt,
            time_range_end=end_dt,
            candle_count=len(candles_df),
            dataset_fingerprint=fingerprint,
            parameters=strategy.parameters,
            feature_definitions=feature_docs,
            signal_timestamps=signal_timestamps,
            total_signals=total_signals,
            buy_signals=buy_signals,
            sell_signals=sell_signals,
            hold_signals=hold_signals,
            created_at=datetime.now(timezone.utc),
        )

        db.add(experiment)

        # Persist individual signal observations
        for sig in signals:
            db_signal = StrategySignal(
                id=str(uuid.uuid4()),
                experiment_id=exp_id,
                strategy_id=sig.strategy_id,
                strategy_version=sig.strategy_version,
                config_id=sig.config_id,
                decision_timestamp=sig.decision_timestamp,
                symbol=sig.symbol,
                side=sig.side.value if isinstance(sig.side, SignalSide) else str(sig.side),
                signal_score=sig.signal_score,
                reference_price=sig.reference_price,
                reason=sig.reason,
                relevant_features=sig.relevant_features,
                created_at=datetime.now(timezone.utc),
            )
            db.add(db_signal)

        await db.commit()
        await db.refresh(experiment)

        logger.info(
            "experiment_persisted",
            experiment_id=exp_id,
            strategy_id=strategy.strategy_id,
            config_id=strategy.config_id,
            signals_count=total_signals,
            buy_signals=buy_signals,
            sell_signals=sell_signals,
        )

        return experiment, signals

    async def get_experiment(
        self,
        db: AsyncSession,
        experiment_id: str,
    ) -> Optional[StrategyExperiment]:
        stmt = select(StrategyExperiment).where(StrategyExperiment.id == experiment_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_experiments(
        self,
        db: AsyncSession,
        strategy_id: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[StrategyExperiment]:
        stmt = select(StrategyExperiment)
        if strategy_id:
            stmt = stmt.where(StrategyExperiment.strategy_id == strategy_id)
        if symbol:
            stmt = stmt.where(StrategyExperiment.symbol == symbol)
        stmt = stmt.order_by(desc(StrategyExperiment.created_at)).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_experiment_signals(
        self,
        db: AsyncSession,
        experiment_id: str,
        limit: int = 500,
    ) -> List[StrategySignal]:
        stmt = (
            select(StrategySignal)
            .where(StrategySignal.experiment_id == experiment_id)
            .order_by(StrategySignal.decision_timestamp.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
