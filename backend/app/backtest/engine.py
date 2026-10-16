from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from app.backtest.accounting import EquitySnapshot, PortfolioLedger, TradeRecord
from app.backtest.analytics import PerformanceReport, calculate_performance
from app.backtest.constants import OrderSide, OrderType, STRESS_SCENARIOS
from app.backtest.cost_model import CostModel
from app.backtest.execution import Order, SimulatedExecutionEngine
from app.backtest.validation import classify_market_regimes
from app.core.logging import get_logger
from app.quant.constants import SignalSide
from app.quant.experiments.tracker import compute_dataset_fingerprint
from app.quant.features.pipeline import FeaturePipeline
from app.quant.strategy.base import BaseStrategy

logger = get_logger("backtest.engine")


@dataclass
class BacktestResult:
    strategy_id: str
    strategy_version: str
    config_id: str
    symbol: str
    interval: str
    dataset_fingerprint: str
    time_range_start: datetime
    time_range_end: datetime
    candle_count: int
    initial_cash: float
    performance: PerformanceReport
    equity_curve: List[EquitySnapshot]
    trades: List[TradeRecord]
    order_history: List[Order]
    cost_assumptions: Dict[str, Any]
    regime_performance: Dict[str, Dict[str, Any]]
    stress_test_results: Dict[str, Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "config_id": self.config_id,
            "symbol": self.symbol,
            "interval": self.interval,
            "dataset_fingerprint": self.dataset_fingerprint,
            "time_range_start": self.time_range_start.isoformat(),
            "time_range_end": self.time_range_end.isoformat(),
            "candle_count": self.candle_count,
            "initial_cash": self.initial_cash,
            "performance": self.performance.to_dict(),
            "equity_curve": [s.to_dict() for s in self.equity_curve],
            "trades": [t.to_dict() for t in self.trades],
            "total_orders": len(self.order_history),
            "cost_assumptions": self.cost_assumptions,
            "regime_performance": self.regime_performance,
            "stress_test_results": self.stress_test_results,
        }


class BacktestEngine:
    """
    Event-Driven Historical Backtesting Engine.
    Enforces:
    - Strictly chronological processing.
    - Decisions generated strictly using information available at that time.
    - Execution strictly at next eligible price (bar t+1 Open).
    - Zero look-ahead bias.
    - Full accounting ledger consistency and cost separation.
    """

    def __init__(
        self,
        cost_model: Optional[CostModel] = None,
        pipeline: Optional[FeaturePipeline] = None,
        execution_delay_bars: int = 0,
        initial_cash: float = 10000.0,
    ):
        self.cost_model = cost_model or CostModel()
        self.pipeline = pipeline or FeaturePipeline()
        self.execution_delay_bars = execution_delay_bars
        self.initial_cash = initial_cash

    def run(
        self,
        strategy: BaseStrategy,
        candles_df: pd.DataFrame,
        run_stress_tests: bool = True,
    ) -> BacktestResult:
        """
        Executes complete event-driven backtest simulation.
        """
        if len(candles_df) < strategy.required_warmup_period:
            raise ValueError(
                f"Insufficient candles ({len(candles_df)}) for strategy warm-up ({strategy.required_warmup_period})"
            )

        symbol = str(candles_df["symbol"].iloc[0]) if "symbol" in candles_df.columns else "BTCUSDT"
        interval = str(candles_df["interval"].iloc[0]) if "interval" in candles_df.columns else "1m"
        fingerprint = compute_dataset_fingerprint(candles_df)

        # 1. Feature Engineering
        features_df = self.pipeline.compute_all_features(candles_df)
        features_df["market_regime"] = classify_market_regimes(features_df)

        # 2. Initialize Ledger and Execution Engine
        ledger = PortfolioLedger(initial_cash=self.initial_cash)
        exec_engine = SimulatedExecutionEngine(
            cost_model=self.cost_model,
            execution_delay_bars=self.execution_delay_bars,
        )

        in_position = False
        n_bars = len(features_df)

        # 3. Chronological Event Loop
        for i in range(n_bars):
            row = features_df.iloc[i]
            candle_dict = {
                "open_time": row["open_time"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
            }

            # A. Process Pending Orders from previous bars against CURRENT bar's Open
            exec_engine.process_next_bar_executions(candle_dict, ledger)

            # B. Record End-of-Bar Portfolio Snapshot (Mark-to-Market at Close)
            current_close = float(row["close"])
            ledger.record_bar_snapshot(
                timestamp=row["open_time"],
                current_prices={symbol: current_close},
            )

            # Update position tracking
            pos = ledger.get_position(symbol)
            in_position = pos.is_open

            # C. Strategy Decision (Evaluation at bar close t using strictly observations <= t)
            if i < strategy.required_warmup_period:
                continue

            side, score, reason, relevant_features = strategy.evaluate_bar(row, in_position)

            # D. Queue Orders for NEXT Bar (t+1) Execution
            if side == SignalSide.BUY and not in_position:
                # Target sizing: allocate 95% of available cash
                target_alloc = ledger.cash * 0.95
                approx_price = current_close * 1.002
                qty = target_alloc / approx_price if approx_price > 0 else 0.0

                if (qty * current_close) >= 10.0:
                    exec_engine.submit_order(
                        symbol=symbol,
                        side=OrderSide.BUY,
                        order_type=OrderType.MARKET,
                        quantity=qty,
                        timestamp=row["open_time"],
                    )

            elif side == SignalSide.SELL and in_position:
                # Sell entire held position
                if pos.quantity > 1e-8:
                    exec_engine.submit_order(
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=pos.quantity,
                        timestamp=row["open_time"],
                    )

        # 4. Compute Performance Analytics
        price_start = float(features_df["open"].iloc[0])
        price_end = float(features_df["close"].iloc[-1])
        perf = calculate_performance(
            equity_curve=ledger.equity_curve,
            trades=ledger.trades,
            initial_cash=self.initial_cash,
            interval=interval,
            price_start=price_start,
            price_end=price_end,
            compute_bootstrap=True,
        )

        # 5. Regime Performance Breakdown
        regime_perf = self._calculate_regime_performance(
            features_df, ledger.equity_curve, ledger.trades
        )

        # 6. Stress Scenarios (if enabled)
        stress_results: Dict[str, Dict[str, Any]] = {}
        if run_stress_tests and len(ledger.trades) > 0:
            stress_results = self._run_stress_scenarios(strategy, candles_df)

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

        return BacktestResult(
            strategy_id=strategy.strategy_id,
            strategy_version=strategy.version,
            config_id=strategy.config_id,
            symbol=symbol,
            interval=interval,
            dataset_fingerprint=fingerprint,
            time_range_start=start_dt,
            time_range_end=end_dt,
            candle_count=len(candles_df),
            initial_cash=self.initial_cash,
            performance=perf,
            equity_curve=ledger.equity_curve,
            trades=ledger.trades,
            order_history=exec_engine.order_history,
            cost_assumptions=self.cost_model.to_dict(),
            regime_performance=regime_perf,
            stress_test_results=stress_results,
        )

    def _calculate_regime_performance(
        self,
        features_df: pd.DataFrame,
        equity_curve: List[EquitySnapshot],
        trades: List[TradeRecord],
    ) -> Dict[str, Dict[str, Any]]:
        """Calculates trade performance segmented across market regimes."""
        if not trades:
            return {}

        results: Dict[str, Dict[str, Any]] = {}
        regime_map = {row["open_time"]: row["market_regime"] for _, row in features_df.iterrows()}

        regimes = ["bullish", "bearish", "high_volatility", "choppy"]
        for r in regimes:
            regime_trades = [
                t for t in trades
                if t.side.value == "sell" and regime_map.get(t.timestamp, "choppy") == r
            ]
            n_t = len(regime_trades)
            net_pnl = sum(t.realized_net_pnl for t in regime_trades)
            wins = sum(1 for t in regime_trades if t.realized_net_pnl > 0)
            results[r] = {
                "trades_count": n_t,
                "net_pnl": round(net_pnl, 4),
                "win_rate_pct": round(wins / n_t * 100.0, 2) if n_t > 0 else 0.0,
            }
        return results

    def _run_stress_scenarios(
        self,
        strategy: BaseStrategy,
        candles_df: pd.DataFrame,
    ) -> Dict[str, Dict[str, Any]]:
        """Re-evaluates strategy under higher-fee and higher-slippage stress scenarios."""
        stress_metrics: Dict[str, Dict[str, Any]] = {}

        for scenario_name, scenario_costs in STRESS_SCENARIOS.items():
            if scenario_name == "baseline":
                continue
            stress_model = CostModel.from_dict(scenario_costs)
            stress_engine = BacktestEngine(
                cost_model=stress_model,
                pipeline=self.pipeline,
                execution_delay_bars=self.execution_delay_bars,
                initial_cash=self.initial_cash,
            )
            # Run without recursive stress testing
            res = stress_engine.run(strategy, candles_df, run_stress_tests=False)
            stress_metrics[scenario_name] = {
                "net_return_pct": res.performance.net_return_pct,
                "max_drawdown_pct": res.performance.max_drawdown_pct,
                "sharpe_ratio": res.performance.sharpe_ratio,
                "total_fees_paid": res.performance.total_fees_paid,
                "total_slippage_paid": res.performance.total_slippage_paid,
            }

        # Also add delayed execution stress (1-bar latency)
        delayed_engine = BacktestEngine(
            cost_model=self.cost_model,
            pipeline=self.pipeline,
            execution_delay_bars=1,
            initial_cash=self.initial_cash,
        )
        res_delayed = delayed_engine.run(strategy, candles_df, run_stress_tests=False)
        stress_metrics["delayed_execution_1bar"] = {
            "net_return_pct": res_delayed.performance.net_return_pct,
            "max_drawdown_pct": res_delayed.performance.max_drawdown_pct,
            "sharpe_ratio": res_delayed.performance.sharpe_ratio,
            "total_fees_paid": res_delayed.performance.total_fees_paid,
            "total_slippage_paid": res_delayed.performance.total_slippage_paid,
        }

        return stress_metrics
