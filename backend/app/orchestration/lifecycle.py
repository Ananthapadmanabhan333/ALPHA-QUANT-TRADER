"""
ALPHA Quant — Phase 6: Core Orchestration Lifecycle Manager.
Coordinates the end-to-end quantitative execution pipeline across 9 mandatory stages:
1. Market-data health check
2. Feature pipeline readiness
3. Strategy scheduling
4. Signal validation
5. Central Risk Gate checks
6. Paper order submission
7. Fill processing & simulation
8. Portfolio accounting & balance updates
9. Event persistence & live broadcast

Enforces explicit task ownership and prevents duplicate scheduler instances.
All trading-related operations remain strictly simulated paper trading.
"""

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.market.models import MarketCandle
from app.market.service import MarketDataService
from app.models.paper import PaperAccount, PaperOrder, PaperPosition, PaperRiskEvent
from app.orchestration.broadcaster import get_broadcaster
from app.orchestration.exceptions import (
    DuplicateSchedulerException,
    FeaturePipelineNotReadyException,
    OrchestrationException,
    StaleMarketDataException,
)
from app.paper.broker import PaperBroker
from app.paper.constants import OrderSide, OrderType
from app.paper.exceptions import (
    EmergencyStopActiveException,
    InsufficientBalanceException,
    LiveTradingForbiddenException,
    RiskBreachException,
    StaleFeedException,
)
from app.paper.schemas import PaperOrderCreateRequest
from app.quant.constants import (
    STRATEGY_MEAN_REVERSION,
    STRATEGY_MOMENTUM,
    STRATEGY_TREND_FOLLOWING,
    SUPPORTED_STRATEGIES,
    SignalSide,
)
from app.quant.features.pipeline import FeaturePipeline
from app.quant.strategy.base import BaseStrategy, Signal
from app.quant.strategy.mean_reversion import MeanReversionStrategy
from app.quant.strategy.momentum import MomentumStrategy
from app.quant.strategy.trend_following import TrendFollowingStrategy

logger = get_logger("orchestration.lifecycle")


class LifecycleStatus(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


class LifecycleManager:
    """
    Central orchestration supervisor for the ALPHA Quant engine.
    Ensures safe, auditable, and idempotent execution of quantitative strategies in simulation.
    """
    def __init__(
        self,
        broker: Optional[PaperBroker] = None,
        market_service: Optional[MarketDataService] = None,
        feature_pipeline: Optional[FeaturePipeline] = None,
    ):
        self.status = LifecycleStatus.STOPPED
        self.worker_id = f"worker_{uuid.uuid4().hex[:8]}"
        self.task_id: Optional[str] = None
        self.strategy_id: Optional[str] = None
        self.symbol: str = "BTCUSDT"
        self.interval: str = "1m"
        self.poll_interval_seconds: float = 5.0
        self.order_size_pct: float = 0.05
        self.parameters: Dict[str, Any] = {}

        self.started_at: Optional[datetime] = None
        self.last_cycle_at: Optional[datetime] = None
        self.cycle_count: int = 0
        self.signals_count: int = 0
        self.orders_count: int = 0
        self.last_error: Optional[str] = None

        self.broker = broker or PaperBroker()
        self.market_service = market_service or MarketDataService()
        self.feature_pipeline = feature_pipeline or FeaturePipeline()
        self.broadcaster = get_broadcaster()

        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._runner_task: Optional[asyncio.Task] = None

    def _instantiate_strategy(self, strategy_id: str, params: Dict[str, Any]) -> BaseStrategy:
        """Instantiates quantitative strategy from registered baseline algorithms."""
        if strategy_id == STRATEGY_TREND_FOLLOWING:
            return TrendFollowingStrategy(parameters=params)
        elif strategy_id == STRATEGY_MEAN_REVERSION:
            return MeanReversionStrategy(parameters=params)
        elif strategy_id == STRATEGY_MOMENTUM:
            return MomentumStrategy(parameters=params)
        raise ValueError(f"Unknown strategy '{strategy_id}'. Supported: {SUPPORTED_STRATEGIES}")

    async def start(
        self,
        strategy_id: str,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        poll_interval_seconds: float = 5.0,
        order_size_pct: float = 0.05,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Starts automated paper trading scheduler loop with explicit task ownership.
        Rejects duplicate scheduler executions if an instance is already running.
        """
        if strategy_id not in SUPPORTED_STRATEGIES:
            raise ValueError(f"Strategy '{strategy_id}' not supported. Supported: {SUPPORTED_STRATEGIES}")

        async with self._lock:
            if self.status in [LifecycleStatus.RUNNING, LifecycleStatus.STARTING]:
                raise DuplicateSchedulerException(
                    f"Duplicate scheduler instance rejected. Lifecycle Manager is already running "
                    f"with task '{self.task_id}' owned by worker '{self.worker_id}' "
                    f"for strategy '{self.strategy_id}'.",
                    details={
                        "existing_task_id": self.task_id,
                        "existing_worker_id": self.worker_id,
                        "existing_strategy": self.strategy_id,
                        "status": self.status.value,
                    },
                )

            self.status = LifecycleStatus.STARTING
            self.task_id = f"orch_{uuid.uuid4().hex[:12]}"
            self.strategy_id = strategy_id
            self.symbol = symbol.replace("/", "").upper()
            self.interval = interval
            self.poll_interval_seconds = max(0.5, poll_interval_seconds)
            self.order_size_pct = min(max(0.001, order_size_pct), 0.10)
            self.parameters = parameters or {}
            self.started_at = datetime.now(timezone.utc)
            self.last_error = None
            self._stop_event.clear()

            # Launch background runner loop
            self._runner_task = asyncio.create_task(self._execution_loop())
            self.status = LifecycleStatus.RUNNING

            logger.info(
                "orchestrator_started",
                task_id=self.task_id,
                worker_id=self.worker_id,
                strategy_id=self.strategy_id,
                symbol=self.symbol,
            )

            # Persist and broadcast start event
            await self._record_system_event(
                event_type="ORCHESTRATOR_START",
                severity="INFO",
                reason=f"Lifecycle Manager started paper loop for {self.strategy_id} on {self.symbol} ({self.interval})",
                metadata={
                    "task_id": self.task_id,
                    "worker_id": self.worker_id,
                    "strategy_id": self.strategy_id,
                    "symbol": self.symbol,
                },
            )

            await self.broadcaster.broadcast(
                "ORCHESTRATOR_START",
                {
                    "task_id": self.task_id,
                    "worker_id": self.worker_id,
                    "strategy_id": self.strategy_id,
                    "symbol": self.symbol,
                    "status": self.status.value,
                },
            )

            return {
                "status": self.status.value,
                "task_id": self.task_id,
                "worker_id": self.worker_id,
                "strategy_id": self.strategy_id,
                "symbol": self.symbol,
                "interval": self.interval,
                "started_at": self.started_at,
                "message": "Automated paper trading lifecycle loop started successfully.",
            }

    async def stop(self) -> Dict[str, Any]:
        """
        Gracefully halts the paper trading loop and releases task ownership.
        """
        async with self._lock:
            if self.status in [LifecycleStatus.STOPPED, LifecycleStatus.STOPPING]:
                return {
                    "status": LifecycleStatus.STOPPED.value,
                    "stopped_at": datetime.now(timezone.utc),
                    "total_cycles": self.cycle_count,
                    "signals_generated": self.signals_count,
                    "orders_submitted": self.orders_count,
                    "message": "Lifecycle Manager is already stopped.",
                }

            self.status = LifecycleStatus.STOPPING
            self._stop_event.set()

            if self._runner_task and not self._runner_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(self._runner_task), timeout=3.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    self._runner_task.cancel()

            self.status = LifecycleStatus.STOPPED
            stopped_time = datetime.now(timezone.utc)

            logger.info("orchestrator_stopped", task_id=self.task_id, cycles=self.cycle_count)

            await self._record_system_event(
                event_type="ORCHESTRATOR_STOP",
                severity="INFO",
                reason=f"Lifecycle Manager stopped. Total cycles: {self.cycle_count}",
                metadata={"cycles": self.cycle_count, "orders": self.orders_count},
            )

            await self.broadcaster.broadcast(
                "ORCHESTRATOR_STOP",
                {
                    "task_id": self.task_id,
                    "status": self.status.value,
                    "cycles": self.cycle_count,
                    "orders": self.orders_count,
                },
            )

            return {
                "status": self.status.value,
                "stopped_at": stopped_time,
                "total_cycles": self.cycle_count,
                "signals_generated": self.signals_count,
                "orders_submitted": self.orders_count,
                "message": "Lifecycle Manager stopped cleanly.",
            }

    async def shutdown(self) -> None:
        """Alias for graceful shutdown on server termination."""
        await self.stop()

    def get_status(self) -> Dict[str, Any]:
        """Returns current operational telemetry and statistics."""
        return {
            "status": self.status.value,
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "interval": self.interval,
            "started_at": self.started_at,
            "last_cycle_at": self.last_cycle_at,
            "cycle_count": self.cycle_count,
            "signals_count": self.signals_count,
            "orders_count": self.orders_count,
            "last_error": self.last_error,
        }

    async def _execution_loop(self) -> None:
        """Background continuous execution loop."""
        session_factory = get_session_factory()
        while not self._stop_event.is_set():
            try:
                async with session_factory() as session:
                    await self.run_single_cycle(session)
            except Exception as exc:
                self.last_error = str(exc)
                logger.error("orchestrator_cycle_error", error=str(exc))

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval_seconds)
            except asyncio.TimeoutError:
                pass

    async def run_single_cycle(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Executes exactly ONE deterministic lifecycle cycle through all 9 stages:
        1. Market-data health
        2. Feature readiness
        3. Strategy scheduling
        4. Signal validation
        5. Central Risk Gate
        6. Paper order submission
        7. Fill processing
        8. Portfolio updates
        9. Event persistence & live broadcast
        """
        strategy_id = self.strategy_id or STRATEGY_TREND_FOLLOWING
        symbol = self.symbol
        interval = self.interval
        cycle_id = f"cycle_{uuid.uuid4().hex[:8]}"

        cycle_result: Dict[str, Any] = {
            "cycle_id": cycle_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "COMPLETED",
            "strategy_id": strategy_id,
            "symbol": symbol,
            "interval": interval,
            "stages": {},
        }

        # -------------------------------------------------------------
        # STAGE 1: Market-Data Health Check
        # -------------------------------------------------------------
        stmt = (
            select(MarketCandle)
            .where(
                MarketCandle.symbol == symbol,
                MarketCandle.interval == interval,
                MarketCandle.is_closed.is_(True),
            )
            .order_by(MarketCandle.open_time.desc())
            .limit(1)
        )
        latest_candle = (await db.execute(stmt)).scalars().first()

        now_utc = datetime.now(timezone.utc)
        if not latest_candle:
            cycle_result["stages"]["stage_1_market_health"] = {"status": "FAILED", "reason": "No market candles found"}
            cycle_result["status"] = "SKIPPED"
            return cycle_result

        close_time = latest_candle.close_time
        if close_time.tzinfo is None:
            close_time = close_time.replace(tzinfo=timezone.utc)

        candle_age = (now_utc - close_time).total_seconds()
        # In testing environments, allow older historical test fixtures without tripping stale feed
        if candle_age > 300.0 and self.broker.risk_gate.max_feed_age_seconds > 0:
            cycle_result["stages"]["stage_1_market_health"] = {
                "status": "STALE",
                "age_seconds": round(candle_age, 2),
                "latest_time": close_time.isoformat(),
            }
            # We record warning and skip trading if feed is stale
            logger.warning("lifecycle_stale_market_feed", symbol=symbol, age_seconds=candle_age)
            cycle_result["status"] = "SKIPPED"
            return cycle_result

        cycle_result["stages"]["stage_1_market_health"] = {
            "status": "HEALTHY",
            "close_price": latest_candle.close,
            "candle_time": close_time.isoformat(),
        }

        # -------------------------------------------------------------
        # STAGE 2: Feature Readiness Check
        # -------------------------------------------------------------
        strategy = self._instantiate_strategy(strategy_id, self.parameters)
        warmup_required = strategy.required_warmup_period

        # Fetch chronological bars for feature generation
        stmt_bars = (
            select(MarketCandle)
            .where(
                MarketCandle.symbol == symbol,
                MarketCandle.interval == interval,
                MarketCandle.is_closed.is_(True),
            )
            .order_by(MarketCandle.open_time.asc())
        )
        all_bars = list((await db.execute(stmt_bars)).scalars().all())

        if len(all_bars) < warmup_required:
            cycle_result["stages"]["stage_2_feature_readiness"] = {
                "status": "INSUFFICIENT_BARS",
                "available": len(all_bars),
                "required": warmup_required,
            }
            cycle_result["status"] = "SKIPPED"
            return cycle_result

        features_df = self.feature_pipeline.compute_features(all_bars)
        cycle_result["stages"]["stage_2_feature_readiness"] = {
            "status": "READY",
            "bars_computed": len(features_df),
        }

        # -------------------------------------------------------------
        # STAGE 3: Strategy Scheduling & Signal Generation
        # -------------------------------------------------------------
        account = await self.broker.get_or_create_default_account(db)
        position = await self.broker.get_position(db, account.id, symbol)
        in_position = position is not None and position.quantity > 0.0

        latest_bar = features_df.iloc[-1]
        side, score, reason, relevant_features = strategy.evaluate_bar(latest_bar, in_position=in_position)
        signal = Signal(
            strategy_id=strategy.strategy_id,
            strategy_version=strategy.version,
            decision_timestamp=datetime.now(timezone.utc),
            symbol=symbol,
            side=side,
            signal_score=score,
            reference_price=float(latest_bar["close"]),
            reason=reason,
            relevant_features=relevant_features,
            config_id=strategy.config_id,
        )
        self.signals_count += 1

        cycle_result["stages"]["stage_3_strategy_scheduling"] = {
            "strategy": strategy.strategy_id,
            "side": signal.side.value if hasattr(signal.side, "value") else str(signal.side),
            "score": signal.signal_score,
            "reason": signal.reason,
            "reference_price": signal.reference_price,
        }

        # -------------------------------------------------------------
        # STAGE 4: Signal Validation
        # -------------------------------------------------------------
        if signal.side == SignalSide.HOLD:
            cycle_result["stages"]["stage_4_signal_validation"] = {"status": "HOLD", "action": "NO_ORDER"}
            self.cycle_count += 1
            self.last_cycle_at = datetime.now(timezone.utc)
            return cycle_result

        if signal.reference_price <= 0.0:
            cycle_result["stages"]["stage_4_signal_validation"] = {"status": "INVALID", "reason": "Non-positive price"}
            cycle_result["status"] = "REJECTED"
            return cycle_result

        cycle_result["stages"]["stage_4_signal_validation"] = {"status": "VALID", "side": signal.side.value}

        # -------------------------------------------------------------
        # STAGE 5: Central Risk Gate Evaluation & Order Sizing
        # -------------------------------------------------------------
        equity = account.virtual_balance
        if position:
            equity += position.quantity * signal.reference_price

        # Calculate position sizing (e.g. 5% of equity)
        target_notional = equity * self.order_size_pct
        target_qty = round(target_notional / signal.reference_price, 4)

        if target_qty <= 0:
            cycle_result["stages"]["stage_5_risk_gate"] = {"status": "REJECTED", "reason": "Target quantity rounds to 0"}
            cycle_result["status"] = "REJECTED"
            return cycle_result

        order_side = OrderSide.BUY if signal.side == SignalSide.BUY else OrderSide.SELL
        if order_side == OrderSide.SELL and (not position or position.quantity < target_qty):
            # Liquidate current available spot balance if selling
            target_qty = position.quantity if position else 0.0

        if target_qty <= 0:
            cycle_result["stages"]["stage_5_risk_gate"] = {"status": "REJECTED", "reason": "No inventory to sell"}
            cycle_result["status"] = "SKIPPED"
            return cycle_result

        # Idempotent order submission ID based on bar close time
        client_order_id = f"orch_{strategy.strategy_id}_{symbol}_{int(latest_candle.close_time.timestamp())}_{order_side.value}"

        order_req = PaperOrderCreateRequest(
            client_order_id=client_order_id,
            symbol=symbol,
            side=order_side,
            order_type=OrderType.MARKET,
            quantity=target_qty,
            price=signal.reference_price,
            is_live=False,
        )

        risk_state = await self.broker.get_account_risk_state(db, account.id)
        try:
            self.broker.risk_gate.check_pre_trade_invariants(
                request=order_req,
                account=account,
                risk_state=risk_state,
                current_position=position,
                current_price=signal.reference_price,
                latest_feed_time=close_time,
            )
            cycle_result["stages"]["stage_5_risk_gate"] = {"status": "PASSED"}
        except Exception as exc:
            cycle_result["stages"]["stage_5_risk_gate"] = {
                "status": "REJECTED",
                "error": str(exc),
                "rule": getattr(exc, "rule_name", "UNKNOWN"),
            }
            cycle_result["status"] = "RISK_REJECTED"

            # Persist risk breach event
            db.add(
                PaperRiskEvent(
                    id=str(uuid.uuid4()),
                    account_id=account.id,
                    event_type="RISK_BREACH",
                    severity="WARNING",
                    reason=f"Lifecycle order rejected by Risk Gate: {str(exc)}",
                    metadata_json={"strategy": strategy_id, "symbol": symbol, "client_order_id": client_order_id},
                )
            )
            await db.commit()
            return cycle_result

        # -------------------------------------------------------------
        # STAGE 6: Paper Order Submission
        # -------------------------------------------------------------
        try:
            order = await self.broker.submit_order(
                db=db,
                request=order_req,
                current_market_price=signal.reference_price,
                latest_feed_time=close_time,
                bar_volume=latest_candle.volume,
            )
            self.orders_count += 1
            cycle_result["stages"]["stage_6_order_submission"] = {
                "order_id": order.id,
                "client_order_id": order.client_order_id,
                "status": order.status,
            }
        except Exception as exc:
            cycle_result["stages"]["stage_6_order_submission"] = {"status": "FAILED", "error": str(exc)}
            cycle_result["status"] = "ERROR"
            return cycle_result

        # -------------------------------------------------------------
        # STAGE 7: Fill Processing
        # -------------------------------------------------------------
        fills = await self.broker.get_order_fills(db, order.id)
        cycle_result["stages"]["stage_7_fill_processing"] = {
            "fills_count": len(fills),
            "filled_quantity": order.filled_quantity,
            "avg_fill_price": order.avg_fill_price,
            "fee": order.fee,
        }

        # -------------------------------------------------------------
        # STAGE 8: Portfolio Accounting & Ledger Updates
        # -------------------------------------------------------------
        await db.refresh(account)
        updated_position = await self.broker.get_position(db, account.id, symbol)
        cycle_result["stages"]["stage_8_portfolio_updates"] = {
            "virtual_cash": account.virtual_balance,
            "position_qty": updated_position.quantity if updated_position else 0.0,
            "realized_pnl": updated_position.realized_pnl if updated_position else 0.0,
        }

        # -------------------------------------------------------------
        # STAGE 9: Event Persistence & Live Telemetry Broadcast
        # -------------------------------------------------------------
        event = PaperRiskEvent(
            id=str(uuid.uuid4()),
            account_id=account.id,
            event_type="ORCHESTRATOR_CYCLE",
            severity="INFO",
            reason=f"Executed {order.side} of {order.filled_quantity} {symbol} at avg {order.avg_fill_price}",
            metadata_json={
                "cycle_id": cycle_id,
                "order_id": order.id,
                "signal_side": signal.side.value,
                "score": signal.signal_score,
            },
        )
        db.add(event)
        await db.commit()

        cycle_result["stages"]["stage_9_event_persistence"] = {"event_id": event.id, "persisted": True}

        # Live broadcast
        await self.broadcaster.broadcast("ORCHESTRATOR_CYCLE", cycle_result)

        self.cycle_count += 1
        self.last_cycle_at = datetime.now(timezone.utc)
        return cycle_result

    async def _record_system_event(
        self,
        event_type: str,
        severity: str,
        reason: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Helper to log lifecycle events into paper_risk_events."""
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                account = await self.broker.get_or_create_default_account(session)
                event = PaperRiskEvent(
                    id=str(uuid.uuid4()),
                    account_id=account.id,
                    event_type=event_type,
                    severity=severity,
                    reason=reason,
                    metadata_json=metadata,
                )
                session.add(event)
                await session.commit()
        except Exception as exc:
            logger.debug("record_system_event_failed", error=str(exc))


# Global singleton lifecycle manager
_lifecycle_manager_instance: Optional[LifecycleManager] = None


def get_lifecycle_manager() -> LifecycleManager:
    global _lifecycle_manager_instance
    if _lifecycle_manager_instance is None:
        _lifecycle_manager_instance = LifecycleManager()
    return _lifecycle_manager_instance
