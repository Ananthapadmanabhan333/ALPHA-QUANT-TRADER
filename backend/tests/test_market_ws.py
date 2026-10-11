import json
import pytest
from app.market.backoff import compute_exponential_backoff_jitter
from app.market.exceptions import CandleValidationException
from app.market.ws_adapter import BinanceWsAdapter


def make_ws_payload(
    symbol: str = "BTCUSDT",
    interval: str = "1m",
    open_time_ms: int = 1700000000000,
    close_time_ms: int = 1700000059999,
    price: float = 62000.0,
    is_closed: bool = False,
) -> str:
    return json.dumps({
        "e": "kline",
        "E": close_time_ms - 10000,
        "s": symbol,
        "k": {
            "t": open_time_ms,
            "T": close_time_ms,
            "s": symbol,
            "i": interval,
            "f": 100,
            "L": 200,
            "o": str(price),
            "c": str(price + 25.0),
            "h": str(price + 50.0),
            "l": str(price - 20.0),
            "v": "1.500",
            "n": 25,
            "x": is_closed,
            "q": "93000.00",
            "V": "0.75",
            "Q": "46500.00",
            "B": "0",
        },
    })


def test_ws_parse_open_candle():
    adapter = BinanceWsAdapter(symbol="BTCUSDT", interval="1m")
    msg = make_ws_payload(is_closed=False)
    candle = adapter.parse_ws_message(msg)

    assert candle["symbol"] == "BTCUSDT"
    assert candle["interval"] == "1m"
    assert candle["is_closed"] is False
    assert candle["open"] == 62000.0
    assert candle["close"] == 62025.0
    assert candle["high"] == 62050.0
    assert candle["low"] == 61980.0
    assert candle["source"] == "binance_spot_ws"
    assert candle["exchange_event_time"] is not None


def test_ws_parse_finalized_candle():
    adapter = BinanceWsAdapter(symbol="BTCUSDT", interval="1m")
    msg = make_ws_payload(is_closed=True)
    candle = adapter.parse_ws_message(msg)

    assert candle["is_closed"] is True


def test_ws_parse_malformed_json():
    adapter = BinanceWsAdapter(symbol="BTCUSDT", interval="1m")
    with pytest.raises(ValueError, match="Malformed JSON"):
        adapter.parse_ws_message("invalid-non-json-payload")


def test_ws_parse_missing_k_object():
    adapter = BinanceWsAdapter(symbol="BTCUSDT", interval="1m")
    with pytest.raises(ValueError, match="missing 'k' object"):
        adapter.parse_ws_message(json.dumps({"e": "ping"}))


def test_ws_parse_invalid_ohlc_math():
    adapter = BinanceWsAdapter(symbol="BTCUSDT", interval="1m")
    # Low > High
    payload = json.loads(make_ws_payload())
    payload["k"]["l"] = "70000.0"  # higher than high 62050
    with pytest.raises(CandleValidationException):
        adapter.parse_ws_message(json.dumps(payload))


def test_exponential_backoff_jitter():
    # Attempt 0 should be <= 1.0
    b0 = compute_exponential_backoff_jitter(0, initial_backoff=1.0, max_backoff=60.0)
    assert 0.0 <= b0 <= 1.0

    # Attempts should increase up to max_backoff
    b5 = compute_exponential_backoff_jitter(5, initial_backoff=1.0, max_backoff=60.0)
    assert 0.1 <= b5 <= 60.0

    # High attempts cap at max_backoff
    b10 = compute_exponential_backoff_jitter(10, initial_backoff=1.0, max_backoff=60.0)
    assert 0.1 <= b10 <= 60.0
