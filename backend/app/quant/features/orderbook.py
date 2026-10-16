"""
Optional Spread and Order-Book Imbalance Feature Calculations.

Formulas:
- Absolute Spread: Spread_t = P_ask,t - P_bid,t
- Relative Spread: RelSpread_t = (P_ask,t - P_bid,t) / MidPrice_t, MidPrice_t = (P_ask,t + P_bid,t) / 2
- Order-Book Imbalance (OBI): OBI_t = (Q_bid,t - Q_ask,t) / (Q_bid,t + Q_ask,t)

Lookback: 1 period (instantaneous at observation timestamp t)
Warm-up Period: 1 period
Timestamp Alignment: Aligned to snapshot timestamp t.

Condition: These features are optional and only computed when trustworthy order-book
or top-of-book depth data is explicitly available. If only OHLCV data is available,
these features return NaN / None with explicit status indication.
"""
from typing import Optional
import numpy as np
import pandas as pd
from app.quant.features.metadata import FeatureDoc


def get_spread_doc() -> FeatureDoc:
    return FeatureDoc(
        name="spread",
        formula="Spread_t = P_ask,t - P_bid,t",
        lookback=1,
        warmup_period=1,
        timestamp_alignment="Aligned to the snapshot timestamp t. Requires trustworthy top-of-book quotes.",
        description="Bid-Ask spread when trustworthy Level 1 / Level 2 book data is available.",
    )


def get_order_book_imbalance_doc() -> FeatureDoc:
    return FeatureDoc(
        name="order_book_imbalance",
        formula="OBI_t = (Q_bid,t - Q_ask,t) / (Q_bid,t + Q_ask,t)",
        lookback=1,
        warmup_period=1,
        timestamp_alignment="Aligned to the snapshot timestamp t. Requires trustworthy Level 1 / Level 2 book data.",
        description="Top-of-book volume imbalance normalized to [-1.0, 1.0].",
    )


def compute_spread(
    ask_price: Optional[pd.Series] = None,
    bid_price: Optional[pd.Series] = None,
    length: int = 0,
) -> pd.Series:
    """
    Computes absolute bid-ask spread if trustworthy quotes are supplied.
    """
    if ask_price is None or bid_price is None:
        # Graceful fallback when only OHLCV is available
        s = pd.Series(np.nan, index=range(length), name="spread")
        return s
    
    spread = ask_price - bid_price
    spread = spread.replace([np.inf, -np.inf], np.nan)
    spread.name = "spread"
    return spread


def compute_order_book_imbalance(
    bid_qty: Optional[pd.Series] = None,
    ask_qty: Optional[pd.Series] = None,
    length: int = 0,
) -> pd.Series:
    """
    Computes Order Book Imbalance (OBI) in [-1.0, 1.0].
    """
    if bid_qty is None or ask_qty is None:
        s = pd.Series(np.nan, index=range(length), name="order_book_imbalance")
        return s

    total_qty = bid_qty + ask_qty
    safe_total = total_qty.replace(0.0, np.nan)
    obi = (bid_qty - ask_qty) / safe_total
    obi = obi.replace([np.inf, -np.inf], np.nan)
    obi.name = "order_book_imbalance"
    return obi
