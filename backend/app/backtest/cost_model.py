from dataclasses import dataclass
from typing import Any, Dict, Tuple
from app.backtest.constants import DEFAULT_COST_MODEL, OrderSide, STRESS_SCENARIOS


@dataclass
class CostModel:
    """
    Institutional Execution Cost Model.
    Explicitly distinguishes and tracks:
    - Gross trading value
    - Exchange trading fees (taker / maker schedules)
    - Adverse execution slippage
    - Spread penalties
    - Liquidity volume constraints
    """
    maker_fee_bps: float = 8.0
    taker_fee_bps: float = 10.0
    slippage_bps: float = 5.0
    assumed_spread_bps: float = 2.0
    max_volume_pct: float = 10.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CostModel":
        merged = {**DEFAULT_COST_MODEL, **data}
        return cls(
            maker_fee_bps=float(merged.get("maker_fee_bps", 8.0)),
            taker_fee_bps=float(merged.get("taker_fee_bps", 10.0)),
            slippage_bps=float(merged.get("slippage_bps", 5.0)),
            assumed_spread_bps=float(merged.get("assumed_spread_bps", 2.0)),
            max_volume_pct=float(merged.get("max_volume_pct", 10.0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "maker_fee_bps": self.maker_fee_bps,
            "taker_fee_bps": self.taker_fee_bps,
            "slippage_bps": self.slippage_bps,
            "assumed_spread_bps": self.assumed_spread_bps,
            "max_volume_pct": self.max_volume_pct,
        }

    def calculate_fill_price(
        self,
        ref_price: float,
        side: OrderSide,
        is_maker: bool = False,
    ) -> Tuple[float, float]:
        """
        Calculates adverse execution fill price incorporating slippage and half-spread.
        Returns: (fill_price, total_slippage_cost_per_unit)
        """
        # Basis point conversion
        slip_pct = (self.slippage_bps if not is_maker else 0.0) / 10000.0
        spread_pct = (self.assumed_spread_bps / 2.0) / 10000.0
        total_penalty_pct = slip_pct + spread_pct

        if side == OrderSide.BUY:
            # Adverse slippage increases buy price
            fill_price = ref_price * (1.0 + total_penalty_pct)
            slippage_cost_per_unit = fill_price - ref_price
        else:
            # Adverse slippage decreases sell price
            fill_price = ref_price * (1.0 - total_penalty_pct)
            slippage_cost_per_unit = ref_price - fill_price

        return fill_price, slippage_cost_per_unit

    def calculate_fee(self, notional: float, is_maker: bool = False) -> float:
        """Calculates exchange fee based on maker/taker schedule."""
        bps = self.maker_fee_bps if is_maker else self.taker_fee_bps
        return notional * (bps / 10000.0)

    def check_liquidity_constraint(
        self,
        order_qty: float,
        candle_volume: float,
    ) -> Tuple[float, bool]:
        """
        Verifies if order quantity exceeds maximum allowed volume participation.
        Returns: (fillable_qty, is_partially_filled)
        """
        if candle_volume <= 0:
            # No volume in candle: cannot fill
            return 0.0, True

        max_allowed_qty = candle_volume * (self.max_volume_pct / 100.0)
        if order_qty <= max_allowed_qty:
            return order_qty, False
        else:
            # Partially fill up to max allowable volume participation
            return max_allowed_qty, True

    def create_stress_model(self, scenario_name: str) -> "CostModel":
        """Instantiates cost model configured for a specified stress scenario."""
        if scenario_name not in STRESS_SCENARIOS:
            raise ValueError(f"Unknown stress scenario '{scenario_name}'")
        return CostModel.from_dict(STRESS_SCENARIOS[scenario_name])
