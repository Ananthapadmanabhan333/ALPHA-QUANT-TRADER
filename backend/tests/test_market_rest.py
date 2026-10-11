from datetime import datetime, timezone, timedelta
import httpx
import pytest
from app.market.exceptions import (
    ExchangeConnectionException,
    InvalidIntervalException,
    RateLimitExceededException,
)
from app.market.rest_adapter import BinanceRestAdapter


def make_binance_raw_kline(open_time_ms: int, close_time_ms: int, price: float = 60000.0) -> list:
    return [
        open_time_ms,
        str(price),
        str(price + 100.0),
        str(price - 100.0),
        str(price + 50.0),
        "10.5000",
        close_time_ms,
        "630000.00",
        150,
        "5.2500",
        "315000.00",
        "0",
    ]


@pytest.mark.asyncio
async def test_rest_fetch_klines_success():
    t0_ms = 1700000000000
    t1_ms = 1700000059999
    mock_payload = [
        make_binance_raw_kline(t0_ms, t1_ms, 61000.0),
        make_binance_raw_kline(t0_ms + 60000, t1_ms + 60000, 61050.0),
    ]

    async def mock_handler(request: httpx.Request):
        assert "api/v3/klines" in str(request.url)
        assert "symbol=BTCUSDT" in str(request.url)
        assert "interval=1m" in str(request.url)
        return httpx.Response(200, json=mock_payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    adapter = BinanceRestAdapter(client=client)

    candles = await adapter.fetch_klines(symbol="BTC/USDT", interval="1m", limit=10)
    assert len(candles) == 2
    assert candles[0]["symbol"] == "BTCUSDT"
    assert candles[0]["interval"] == "1m"
    assert candles[0]["open"] == 61000.0
    assert candles[0]["high"] == 61100.0
    assert candles[0]["is_closed"] is True
    assert candles[0]["source"] == "binance_spot"
    assert isinstance(candles[0]["open_time"], datetime)
    assert candles[0]["open_time"].tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_rest_rate_limit_429():
    async def mock_handler(request: httpx.Request):
        return httpx.Response(429, headers={"Retry-After": "30"}, text="Rate limit exceeded")

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    adapter = BinanceRestAdapter(client=client)

    with pytest.raises(RateLimitExceededException) as exc_info:
        await adapter.fetch_klines(symbol="BTCUSDT", interval="1m")
    assert exc_info.value.status_code == 429
    assert exc_info.value.details["retry_after_seconds"] == 30.0


@pytest.mark.asyncio
async def test_rest_network_error():
    async def mock_handler(request: httpx.Request):
        raise httpx.ConnectError("Connection refused by peer")

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    adapter = BinanceRestAdapter(client=client)

    with pytest.raises(ExchangeConnectionException, match="Network error"):
        await adapter.fetch_klines(symbol="BTCUSDT", interval="1m")


@pytest.mark.asyncio
async def test_rest_invalid_interval():
    adapter = BinanceRestAdapter()
    with pytest.raises(InvalidIntervalException):
        await adapter.fetch_klines(symbol="BTCUSDT", interval="30m")


@pytest.mark.asyncio
async def test_rest_fetch_range_pagination():
    base_time_ms = 1700000000000

    async def mock_handler(request: httpx.Request):
        start_param = int(request.url.params.get("startTime", base_time_ms))
        # Return 2 candles starting at start_param
        items = [
            make_binance_raw_kline(start_param, start_param + 59999, 60000.0),
            make_binance_raw_kline(start_param + 60000, start_param + 119999, 60100.0),
        ]
        return httpx.Response(200, json=items)

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    adapter = BinanceRestAdapter(client=client)

    start_dt = datetime.fromtimestamp(base_time_ms / 1000.0, tz=timezone.utc)
    end_dt = start_dt + timedelta(minutes=4)

    candles = await adapter.fetch_range(
        symbol="BTCUSDT",
        interval="1m",
        start_time=start_dt,
        end_time=end_dt,
        max_candles=4,
    )
    assert len(candles) >= 2
    assert candles[0]["open_time"] == start_dt
