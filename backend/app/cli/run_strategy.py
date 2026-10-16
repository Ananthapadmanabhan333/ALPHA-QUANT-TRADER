import argparse
import asyncio
import json
from pathlib import Path
import sys

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import get_session_factory, close_database_connection
from app.market.service import MarketDataService
from app.quant.constants import (
    STRATEGY_MEAN_REVERSION,
    STRATEGY_MOMENTUM,
    STRATEGY_TREND_FOLLOWING,
    SUPPORTED_STRATEGIES,
)
from app.quant.experiments.tracker import ExperimentService
from app.quant.features.pipeline import FeaturePipeline


async def main():
    parser = argparse.ArgumentParser(
        description="ALPHA Quant — Strategy Experiment Runner (Audit & Signal Generation Only)"
    )
    parser.add_argument(
        "--strategy",
        type=str,
        required=True,
        choices=SUPPORTED_STRATEGIES,
        help="Strategy identifier",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTCUSDT",
        help="Trading pair symbol (default: BTCUSDT)",
    )
    parser.add_argument(
        "--interval",
        type=str,
        default="1m",
        choices=["1m", "5m", "15m"],
        help="Candle interval (default: 1m)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=300,
        help="Number of historical candles to evaluate (default: 300)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Optional path to output experiment JSON file",
    )

    # Strategy parameter overrides
    parser.add_argument("--fast-window", type=int, default=None)
    parser.add_argument("--slow-window", type=int, default=None)
    parser.add_argument("--zscore-threshold", type=float, default=None)
    parser.add_argument("--tx-cost-bps", type=float, default=None)

    args = parser.parse_args()

    custom_params = {}
    if args.fast_window:
        custom_params["fast_window"] = args.fast_window
    if args.slow_window:
        custom_params["slow_window"] = args.slow_window
    if args.zscore_threshold:
        custom_params["zscore_entry_threshold"] = args.zscore_threshold
    if args.tx_cost_bps:
        custom_params["transaction_cost_bps"] = args.tx_cost_bps

    print("=" * 70)
    print("ALPHA QUANT — STRATEGY EXPERIMENT RUNNER")
    print("Zero-Execution Mode: Strictly signal generation & experiment tracking")
    print("=" * 70)
    print(f"Strategy: {args.strategy}")
    print(f"Symbol:   {args.symbol}")
    print(f"Interval: {args.interval}")
    print(f"Limit:    {args.limit} candles")
    print("-" * 70)

    market_service = MarketDataService()
    pipeline = FeaturePipeline()
    experiment_service = ExperimentService(pipeline)

    session_factory = get_session_factory()
    try:
        async with session_factory() as db:
            candles = await market_service.get_candles(
            db=db,
            symbol=args.symbol,
            interval=args.interval,
            limit=args.limit,
            only_closed=True,
        )

        if not candles:
            print(f"ERROR: No stored finalized candles found for {args.symbol} ({args.interval}).")
            print("Please run historical ingestion first:")
            print(f"  python -m app.cli.ingest --symbol {args.symbol} --interval {args.interval}")
            sys.exit(1)

        print(f"Loaded {len(candles)} finalized candles from storage.")
        print(f"Time Range: {candles[0].open_time.isoformat()} -> {candles[-1].open_time.isoformat()}")

        candles_df = pipeline.candles_to_dataframe(candles, interval=args.interval)

        experiment, signals = await experiment_service.execute_and_persist_experiment(
            db=db,
            strategy_id=args.strategy,
            candles_df=candles_df,
            parameters=custom_params if custom_params else None,
        )

        print("-" * 70)
        print("EXPERIMENT PERSISTED SUCCESSFULLY")
        print(f"Experiment ID:       {experiment.id}")
        print(f"Config ID:           {experiment.config_id}")
        print(f"Dataset Fingerprint: {experiment.dataset_fingerprint}")
        print(f"Total Signals:       {experiment.total_signals}")
        print(f"  - BUY Signals:     {experiment.buy_signals}")
        print(f"  - SELL Signals:    {experiment.sell_signals}")
        print(f"  - HOLD Signals:    {experiment.hold_signals}")
        print("-" * 70)

        # Print last 5 signals for inspection
        print("Recent Signals:")
        for s in signals[-5:]:
            print(
                f"  [{s.decision_timestamp.isoformat()}] {s.side.value.upper():4s} "
                f"Score={s.signal_score:+.2f} RefPrice={s.reference_price:.2f} | {s.reason}"
            )
        print("=" * 70)

        if args.output_json:
            out_data = {
                "experiment_id": experiment.id,
                "strategy_id": experiment.strategy_id,
                "dataset_fingerprint": experiment.dataset_fingerprint,
                "total_signals": experiment.total_signals,
                "buy_signals": experiment.buy_signals,
                "sell_signals": experiment.sell_signals,
                "hold_signals": experiment.hold_signals,
                "parameters": experiment.parameters,
                "signals": [s.to_dict() for s in signals],
            }
            with open(args.output_json, "w", encoding="utf-8") as f:
                json.dump(out_data, f, indent=2)
            print(f"Wrote experiment report to {args.output_json}")
    finally:
        await close_database_connection()


if __name__ == "__main__":
    asyncio.run(main())
