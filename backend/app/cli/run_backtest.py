import argparse
import asyncio
import json
from pathlib import Path
import sys

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.backtest.schemas import BacktestCreateRequest
from app.backtest.service import BacktestService
from app.db.session import close_database_connection, get_session_factory
from app.quant.constants import SUPPORTED_STRATEGIES


async def main():
    parser = argparse.ArgumentParser(
        description="ALPHA Quant — Historical Backtest Runner (Event-Driven Simulation)"
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
        help="Number of historical candles to backtest (default: 300)",
    )
    parser.add_argument(
        "--cash",
        type=float,
        default=10000.0,
        help="Initial capital in USD/USDT (default: 10,000)",
    )
    parser.add_argument(
        "--taker-fee-bps",
        type=float,
        default=10.0,
        help="Taker fee in basis points (default: 10.0 bps = 0.10%)",
    )
    parser.add_argument(
        "--slippage-bps",
        type=float,
        default=5.0,
        help="Adverse execution slippage in basis points (default: 5.0 bps)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Optional path to output backtest JSON report",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("ALPHA QUANT — HISTORICAL EVENT-DRIVEN BACKTEST RUNNER")
    print("=" * 70)
    print(f"Strategy:    {args.strategy}")
    print(f"Symbol:      {args.symbol}")
    print(f"Interval:    {args.interval}")
    print(f"Candles:     {args.limit}")
    print(f"Initial Cash: ${args.cash:,.2f}")
    print(f"Costs:       Taker Fee={args.taker_fee_bps} bps | Slippage={args.slippage_bps} bps")
    print("-" * 70)

    request = BacktestCreateRequest(
        strategy_id=args.strategy,
        symbol=args.symbol,
        interval=args.interval,
        limit=args.limit,
        initial_cash=args.cash,
        cost_model={
            "taker_fee_bps": args.taker_fee_bps,
            "slippage_bps": args.slippage_bps,
        },
    )

    session_factory = get_session_factory()
    service = BacktestService()

    try:
        async with session_factory() as db:
            run_record, result = await service.execute_and_persist_backtest(db, request)

            perf = result.performance
            print("BACKTEST SIMULATION COMPLETED")
            print(f"Run ID:              {run_record.id}")
            print(f"Config ID:           {run_record.config_id}")
            print(f"Dataset Fingerprint: {run_record.dataset_fingerprint}")
            print(f"Candles Evaluated:   {run_record.candle_count}")
            print(f"Time Range:          {run_record.time_range_start.isoformat()} -> {run_record.time_range_end.isoformat()}")
            print("-" * 70)
            print("PERFORMANCE & RISK METRICS:")
            print(f"  Final Equity:      ${perf.final_equity:,.2f}")
            print(f"  Net Total Return:  {perf.net_return_pct:+.2f}%")
            print(f"  Gross Return:      {perf.gross_return_pct:+.2f}%")
            print(f"  Buy & Hold Return: {perf.buy_and_hold_return_pct:+.2f}%")
            print(f"  Max Drawdown:      {perf.max_drawdown_pct:.2f}%")
            print(f"  Sharpe Ratio:      {perf.sharpe_ratio:.2f} ({perf.annualization_assumptions})")
            print(f"  Sortino Ratio:     {perf.sortino_ratio:.2f}")
            print(f"  Annualized Vol:    {perf.annualized_volatility:.2f}%")
            print("-" * 70)
            print("TRADE EXECUTION STATISTICS:")
            print(f"  Total Trades:      {perf.total_trades} (Wins: {perf.winning_trades}, Losses: {perf.losing_trades})")
            print(f"  Win Rate:          {perf.win_rate_pct:.1f}%")
            print(f"  Profit Factor:     {perf.profit_factor if perf.profit_factor is not None else 'N/A'}")
            print(f"  Expectancy:        ${perf.expectancy:.4f} per trade")
            print(f"  Turnover:          {perf.turnover:.2f}x initial capital")
            print(f"  Market Exposure:   {perf.market_exposure_pct:.1f}% of time in position")
            print("-" * 70)
            print("EXECUTION COST IMPACT:")
            print(f"  Total Fees Paid:   ${perf.total_fees_paid:.2f} ({perf.fee_drag_pct:.2f}% drag)")
            print(f"  Total Slippage:    ${perf.total_slippage_paid:.2f} ({perf.slippage_drag_pct:.2f}% drag)")
            print("=" * 70)

            if result.stress_test_results:
                print("STRESS TEST SENSITIVITY ANALYSIS:")
                for scenario, metrics in result.stress_test_results.items():
                    print(
                        f"  [{scenario:22s}] Net Return={metrics['net_return_pct']:+6.2f}% | "
                        f"MaxDD={metrics['max_drawdown_pct']:5.2f}% | "
                        f"Fees=${metrics['total_fees_paid']:6.2f} | "
                        f"Slippage=${metrics['total_slippage_paid']:6.2f}"
                    )
                print("=" * 70)

            if args.output_json:
                with open(args.output_json, "w", encoding="utf-8") as f:
                    json.dump(result.to_dict(), f, indent=2)
                print(f"Wrote full backtest report to {args.output_json}")

    except Exception as e:
        print(f"ERROR executing backtest: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await close_database_connection()


if __name__ == "__main__":
    asyncio.run(main())
