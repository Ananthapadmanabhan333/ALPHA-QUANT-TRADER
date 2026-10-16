from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
import pandas as pd

from app.quant.constants import SignalSide
from app.quant.exceptions import InsufficientDataException


@dataclass(frozen=True)
class Signal:
    """
    Immutable, typed quantitative decision signal.
    Strategies emit signals; they NEVER place orders or modify balances.
    """
    strategy_id: str
    strategy_version: str
    decision_timestamp: datetime
    symbol: str
    side: SignalSide
    signal_score: float
    reference_price: float
    reason: str
    relevant_features: Dict[str, Optional[float]]
    config_id: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["decision_timestamp"] = self.decision_timestamp.isoformat()
        data["side"] = self.side.value if isinstance(self.side, SignalSide) else str(self.side)
        return data


def generate_config_id(strategy_id: str, version: str, params: Dict[str, Any]) -> str:
    """Deterministic configuration hash for parameter tracking."""
    serialized = json.dumps(params, sort_keys=True, default=str)
    raw = f"{strategy_id}:{version}:{serialized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


class BaseStrategy(ABC):
    """
    Abstract base class for quantitative research strategies.
    Long-only spot research initially.
    Deterministic, auditable, with explicit exit conditions.
    """

    def __init__(
        self,
        strategy_id: str,
        version: str,
        parameters: Dict[str, Any],
    ):
        self._strategy_id = strategy_id
        self._version = version
        self._parameters = parameters
        self._config_id = generate_config_id(strategy_id, version, parameters)

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    @property
    def version(self) -> str:
        return self._version

    @property
    def config_id(self) -> str:
        return self._config_id

    @property
    def parameters(self) -> Dict[str, Any]:
        return self._parameters

    @property
    @abstractmethod
    def required_warmup_period(self) -> int:
        """Minimum number of observations required before generating first valid signal."""
        pass

    @abstractmethod
    def evaluate_bar(
        self,
        current_bar: pd.Series,
        in_position: bool,
    ) -> tuple[SignalSide, float, str, Dict[str, Optional[float]]]:
        """
        Evaluates a single chronological bar.

        Returns:
            (side, score, reason, relevant_features)
        """
        pass

    def generate_signals(self, features_df: pd.DataFrame) -> List[Signal]:
        """
        Iterates chronologically through features DataFrame and generates deterministic signals.
        Enforces look-ahead bias prevention: evaluation at row i sees strictly row i.
        """
        if len(features_df) < self.required_warmup_period:
            raise InsufficientDataException(
                f"Strategy {self.strategy_id} requires at least {self.required_warmup_period} "
                f"bars for warm-up, but received {len(features_df)} bars."
            )

        signals: List[Signal] = []
        in_position = False
        symbol = features_df["symbol"].iloc[0] if "symbol" in features_df.columns else "BTCUSDT"

        for idx, row in features_df.iterrows():
            # Observations during warm-up period emit explicit HOLD
            if idx < self.required_warmup_period:
                ts = row["open_time"]
                if isinstance(ts, pd.Timestamp):
                    ts = ts.to_pydatetime()
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)

                signals.append(
                    Signal(
                        strategy_id=self.strategy_id,
                        strategy_version=self.version,
                        decision_timestamp=ts,
                        symbol=symbol,
                        side=SignalSide.HOLD,
                        signal_score=0.0,
                        reference_price=float(row["close"]),
                        reason=f"Warm-up period active (bar {idx+1}/{self.required_warmup_period})",
                        relevant_features={},
                        config_id=self.config_id,
                    )
                )
                continue

            side, score, reason, relevant_features = self.evaluate_bar(row, in_position)

            # State transition for long-only spot
            if side == SignalSide.BUY:
                in_position = True
            elif side == SignalSide.SELL:
                in_position = False

            ts = row["open_time"]
            if isinstance(ts, pd.Timestamp):
                ts = ts.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    strategy_version=self.version,
                    decision_timestamp=ts,
                    symbol=symbol,
                    side=side,
                    signal_score=float(score),
                    reference_price=float(row["close"]),
                    reason=reason,
                    relevant_features=relevant_features,
                    config_id=self.config_id,
                )
            )

        return signals
