from datetime import timezone
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from app.market.constants import INTERVAL_TO_SECONDS
from app.market.models import MarketCandle
from app.market.validator import detect_missing_intervals
from app.quant.exceptions import (
    DataIntegrityException,
    InsufficientDataException,
)
from app.quant.features.atr import compute_atr, get_atr_doc
from app.quant.features.metadata import FeatureDoc
from app.quant.features.momentum import (
    compute_momentum,
    get_momentum_doc,
)
from app.quant.features.moving_averages import (
    compute_ema,
    compute_sma,
    get_ema_doc,
    get_sma_doc,
)
from app.quant.features.orderbook import (
    compute_order_book_imbalance,
    compute_spread,
    get_order_book_imbalance_doc,
    get_spread_doc,
)
from app.quant.features.returns import (
    compute_log_returns,
    compute_simple_returns,
    get_log_return_doc,
    get_simple_return_doc,
)
from app.quant.features.volatility import (
    compute_rolling_volatility,
    get_volatility_doc,
)
from app.quant.features.volume import (
    compute_volume_ratio,
    compute_volume_sma,
    compute_volume_zscore,
    get_volume_ratio_doc,
    get_volume_sma_doc,
    get_volume_zscore_doc,
)
from app.quant.features.zscores import (
    compute_rolling_zscore,
    get_zscore_doc,
)


class FeaturePipeline:
    """
    Quantitative Feature Pipeline.

    Enforces:
    - Strict chronological order (ascending open_time).
    - Rejection/exclusion of incomplete/open candles (is_closed=False).
    - Sequence gap detection.
    - Zero look-ahead bias: row t depends strictly on rows <= t.
    - Explicit NaN and infinity sanitization.
    - Complete feature documentation registry.
    """

    def __init__(
        self,
        strict_gap_check: bool = False,
    ):
        self.strict_gap_check = strict_gap_check
        self.feature_docs: Dict[str, FeatureDoc] = {}

    def candles_to_dataframe(
        self,
        candles: List[Union[MarketCandle, Dict[str, Any]]],
        interval: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Validates, filters, and transforms raw candles into an analytical pandas DataFrame.
        """
        if not candles:
            raise InsufficientDataException("Cannot build feature pipeline from empty candle set.")

        rows = []
        for c in candles:
            if isinstance(c, MarketCandle):
                row = {
                    "open_time": c.open_time,
                    "close_time": c.close_time,
                    "open": float(c.open),
                    "high": float(c.high),
                    "low": float(c.low),
                    "close": float(c.close),
                    "volume": float(c.volume),
                    "is_closed": bool(c.is_closed),
                    "symbol": c.symbol,
                    "interval": c.interval,
                }
            else:
                row = {
                    "open_time": c["open_time"],
                    "close_time": c["close_time"],
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                    "volume": float(c["volume"]),
                    "is_closed": bool(c.get("is_closed", True)),
                    "symbol": c.get("symbol", "BTCUSDT"),
                    "interval": c.get("interval", interval or "1m"),
                }
            rows.append(row)

        df = pd.DataFrame(rows)

        # 1. Enforce UTC timezone awareness on open_time
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], utc=True)

        # 2. Incomplete candle filtering: strictly reject open candles
        unclosed_mask = ~df["is_closed"]
        if unclosed_mask.any():
            # Incomplete candles must not leak into historical features
            df = df[df["is_closed"]].copy()
            if df.empty:
                raise InsufficientDataException("All supplied candles were unclosed/incomplete.")

        # 3. Sort chronologically and verify ascending ordering
        df = df.sort_values("open_time").reset_index(drop=True)

        # 4. Check for duplicate timestamps
        if df["open_time"].duplicated().any():
            raise DataIntegrityException("Duplicate candle open_time timestamps detected in dataset.")

        # 5. Check for sequence gaps
        eff_interval = interval or (df["interval"].iloc[0] if "interval" in df.columns else "1m")
        if self.strict_gap_check and eff_interval in INTERVAL_TO_SECONDS:
            # Reconstruct dummy candle list to invoke validator
            gaps = detect_missing_intervals(
                [type("C", (), {"open_time": t})() for t in df["open_time"]],
                eff_interval,
            )
            if gaps:
                raise DataIntegrityException(
                    f"Detected {len(gaps)} sequence gap(s) in input candles for interval {eff_interval}."
                )

        return df

    def compute_all_features(
        self,
        df: pd.DataFrame,
        sma_windows: List[int] = (20, 100),
        ema_windows: List[int] = (20, 100),
        volatility_windows: List[int] = (20,),
        zscore_windows: List[int] = (60,),
        atr_windows: List[int] = (14,),
        volume_windows: List[int] = (20,),
        momentum_periods: List[int] = (5, 15, 60),
    ) -> pd.DataFrame:
        """
        Computes the complete suite of quantitative features and registers their documentation.
        """
        if df.empty:
            raise InsufficientDataException("Cannot compute features on empty DataFrame.")

        features_df = df.copy()
        close = features_df["close"]
        high = features_df["high"]
        low = features_df["low"]
        volume = features_df["volume"]

        # Simple and Logarithmic Returns
        features_df["simple_return"] = compute_simple_returns(close)
        self.feature_docs["simple_return"] = get_simple_return_doc("close")

        features_df["log_return"] = compute_log_returns(close)
        self.feature_docs["log_return"] = get_log_return_doc("close")

        # Simple Moving Averages
        for w in sma_windows:
            col = f"sma_{w}"
            features_df[col] = compute_sma(close, w)
            self.feature_docs[col] = get_sma_doc(w, "close")

        # Exponential Moving Averages
        for w in ema_windows:
            col = f"ema_{w}"
            features_df[col] = compute_ema(close, w)
            self.feature_docs[col] = get_ema_doc(w, "close")

        # Rolling Volatility
        for w in volatility_windows:
            col = f"volatility_{w}"
            features_df[col] = compute_rolling_volatility(close, w)
            self.feature_docs[col] = get_volatility_doc(w, "close")

        # Rolling Z-scores
        for w in zscore_windows:
            col = f"zscore_{w}"
            features_df[col] = compute_rolling_zscore(close, w)
            self.feature_docs[col] = get_zscore_doc(w, "close")

        # Average True Range
        for w in atr_windows:
            col = f"atr_{w}"
            features_df[col] = compute_atr(high, low, close, w)
            self.feature_docs[col] = get_atr_doc(w)

        # Volume Statistics
        for w in volume_windows:
            col_sma = f"volume_sma_{w}"
            col_ratio = f"volume_ratio_{w}"
            col_z = f"volume_zscore_{w}"
            features_df[col_sma] = compute_volume_sma(volume, w)
            features_df[col_ratio] = compute_volume_ratio(volume, w)
            features_df[col_z] = compute_volume_zscore(volume, w)
            self.feature_docs[col_sma] = get_volume_sma_doc(w)
            self.feature_docs[col_ratio] = get_volume_ratio_doc(w)
            self.feature_docs[col_z] = get_volume_zscore_doc(w)

        # Multi-Period Momentum
        for p in momentum_periods:
            col = f"momentum_{p}"
            features_df[col] = compute_momentum(close, p)
            self.feature_docs[col] = get_momentum_doc(p, "close")

        # Optional Spread & Order-Book Imbalance (safe fallback for OHLCV)
        features_df["spread"] = compute_spread(None, None, len(features_df))
        self.feature_docs["spread"] = get_spread_doc()

        features_df["order_book_imbalance"] = compute_order_book_imbalance(None, None, len(features_df))
        self.feature_docs["order_book_imbalance"] = get_order_book_imbalance_doc()

        # Sanitize any residual infinities to NaN
        numeric_cols = features_df.select_dtypes(include=[np.number]).columns
        features_df[numeric_cols] = features_df[numeric_cols].replace([np.inf, -np.inf], np.nan)

        return features_df

    def get_feature_documentation(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns serializable dictionary of all feature formulas, lookbacks, warm-ups, and alignments.
        """
        return {name: doc.to_dict() for name, doc in self.feature_docs.items()}
