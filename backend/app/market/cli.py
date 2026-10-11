import argparse
import asyncio
from datetime import datetime, timezone, timedelta
import sys
from app.core.logging import setup_logging, get_logger
from app.db.session import get_session_factory, close_database_connection
from app.market.constants import (
    DEFAULT_INTERVAL,
    DEFAULT_SYMBOL,
    SUPPORTED_INTERVALS,
    normalize_symbol,
)
from app.market.rest_adapter import BinanceRestAdapter
from app.market.service import MarketDataService
from app.market.ws_adapter import BinanceWsAdapter

logger = get_logger("market.cli")


def parse_date(date_str: str) -> datetime:
    """Parses date string in ISO format or YYYY-MM-DD."""
    date_str = date_str.strip()
    try:
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str)
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date format '{date_str}'. Expected 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS'. Error: {exc}"
        )


async def run_ingestion(
    symbol: str,
    interval: str,
    start_time: datetime,
    end_time: datetime,
    stream: bool = False,
) -> None:
    setup_logging()
    norm_symbol = normalize_symbol(symbol)
    logger.info(
        "starting_market_data_ingestion",
        symbol=norm_symbol,
        interval=interval,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        stream=stream,
    )

    rest_adapter = BinanceRestAdapter()
    service = MarketDataService(rest_adapter=rest_adapter)
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            logger.info("initiating_historical_rest_download")
            saved = await service.backfill_range(
                db=session,
                symbol=norm_symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
            )
            print(f"[SUCCESS] Historical ingestion completed: {saved} candles saved to database for {norm_symbol} ({interval}).")

            # Check if any gaps exist in the ingested range
            gaps = await service.detect_gaps_in_db(
                db=session,
                symbol=norm_symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
            )
            if gaps:
                print(f"[WARNING] Detected {len(gaps)} sequence gaps in requested range:")
                for gap_start, gap_end in gaps[:5]:
                    print(f"  - Missing interval: {gap_start.isoformat()} to {gap_end.isoformat()}")
                if len(gaps) > 5:
                    print(f"  ... and {len(gaps) - 5} more gaps.")
            else:
                print("[SUCCESS] No missing intervals detected in the specified range. Complete sequence verified.")

        except Exception as exc:
            logger.error("historical_ingestion_failed", error=str(exc))
            print(f"[ERROR] Ingestion failed: {exc}", file=sys.stderr)
            raise

    # If stream flag is specified, connect to live WebSocket
    if stream:
        print(f"[INFO] Launching live WebSocket stream for {norm_symbol} ({interval})... Press CTRL+C to terminate.")
        
        async def on_ws_candle(candle: dict):
            async with session_factory() as live_session:
                await service.save_candles(live_session, [candle])
                status_label = "FINALIZED" if candle["is_closed"] else "OPEN"
                print(
                    f"[LIVE WS] {candle['symbol']} {candle['interval']} | "
                    f"Time: {candle['open_time'].strftime('%H:%M:%S')} | "
                    f"Close: {candle['close']} | Vol: {candle['volume']} | [{status_label}]"
                )

        ws_adapter = BinanceWsAdapter(
            symbol=norm_symbol,
            interval=interval,
            on_candle=on_ws_candle,
            tracker=service.tracker,
        )
        task = ws_adapter.start()
        try:
            await task
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n[INFO] Gracefully shutting down live stream...")
            await ws_adapter.stop()

    await close_database_connection()


def main():
    parser = argparse.ArgumentParser(
        description="ALPHA Quant - Public Market Data Ingestion Tool (Binance Spot)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=DEFAULT_SYMBOL,
        help="Trading pair symbol (e.g. BTCUSDT, BTC/USDT)",
    )
    parser.add_argument(
        "--interval",
        type=str,
        default=DEFAULT_INTERVAL,
        choices=SUPPORTED_INTERVALS,
        help="Candle interval (1m, 5m, 15m)",
    )
    parser.add_argument(
        "--start",
        type=parse_date,
        default=(datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d"),
        help="Start date/time (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    )
    parser.add_argument(
        "--end",
        type=parse_date,
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="End date/time (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Continuously stream live market updates via WebSocket after backfill",
    )

    args = parser.parse_args()
    asyncio.run(
        run_ingestion(
            symbol=args.symbol,
            interval=args.interval,
            start_time=args.start,
            end_time=args.end,
            stream=args.stream,
        )
    )


if __name__ == "__main__":
    main()
