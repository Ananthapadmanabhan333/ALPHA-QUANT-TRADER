"""
Pydantic schemas for ALPHA Quant Phase 5 Paper Execution & Risk Subsystem.
Strict validation contracts for order creation, execution status, and risk management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

from app.paper.constants import OrderSide, OrderType, OrderStatus


class PaperOrderCreateRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT", description="Trading pair symbol")
    side: OrderSide = Field(description="Order side: buy or sell")
    order_type: OrderType = Field(default=OrderType.MARKET, description="Order execution type: market or limit")
    quantity: float = Field(gt=0, description="Order quantity in base asset")
    price: Optional[float] = Field(default=None, description="Limit price (mandatory for limit orders)")
    client_order_id: Optional[str] = Field(default=None, description="Unique client-assigned order ID for idempotency")
    current_market_price: Optional[float] = Field(default=None, description="Current market price if matching without DB candle")
    is_live: Optional[bool] = Field(
        default=False,
        description="Live trading flag. Safety invariant: Live execution is strictly forbidden and rejected.",
    )

    @model_validator(mode="after")
    def validate_order(self):
        # Safety invariant check
        if self.is_live:
            raise ValueError("Live trading is strictly prohibited. ALPHA Quant supports simulated paper execution only.")

        if self.order_type == OrderType.LIMIT and (self.price is None or self.price <= 0):
            raise ValueError("Limit orders require a valid positive limit price.")

        return self


class PaperOrderResponse(BaseModel):
    id: str
    client_order_id: str
    account_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None
    filled_quantity: float
    avg_fill_price: Optional[float] = None
    status: str
    fee: float
    slippage_cost: float
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PaperFillResponse(BaseModel):
    id: str
    order_id: str
    symbol: str
    side: str
    fill_price: float
    quantity: float
    gross_notional: float
    fee: float
    slippage_cost: float
    realized_pnl: float
    created_at: datetime


class PaperPositionResponse(BaseModel):
    symbol: str
    quantity: float
    avg_entry_price: float
    cost_basis: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl: float


class PaperAccountResponse(BaseModel):
    account_id: str
    name: str
    virtual_balance: float
    currency: str
    total_positions_value: float
    total_equity: float
    unrealized_pnl: float
    realized_pnl: float
    positions: List[PaperPositionResponse]
    is_active: bool
    created_at: datetime


class RiskStatusResponse(BaseModel):
    emergency_stop: bool
    kill_switch_reason: Optional[str] = None
    max_order_notional: float
    max_position_pct: float
    max_portfolio_exposure_pct: float
    daily_loss_limit_pct: float
    max_drawdown_limit_pct: float
    consecutive_loss_limit: int
    starting_daily_equity: float
    current_daily_pnl: float
    peak_equity: float
    current_drawdown_pct: float
    consecutive_losses: int
    last_breach_reason: Optional[str] = None
    feed_status: str
    last_feed_time: Optional[datetime] = None
    is_trading_allowed: bool


class EmergencyStopRequest(BaseModel):
    reason: str = Field(min_length=3, description="Operational reason for triggering emergency pause")


class EmergencyResumeRequest(BaseModel):
    confirmation: str = Field(description="Must match CONFIRM_RESUME to unpause trading")
    reset_consecutive_losses: bool = Field(default=False, description="Optionally reset consecutive losses counter")


class MarketPriceUpdateRequest(BaseModel):
    symbol: str = "BTCUSDT"
    price: float = Field(gt=0, description="Latest market price")
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None
    timestamp: Optional[datetime] = None


class PaperAccountResetRequest(BaseModel):
    initial_cash: float = Field(default=10000.0, ge=100.0, le=10000000.0, description="New virtual USDT starting capital")
    clear_history: bool = Field(default=True, description="Clear historical paper orders and fills")

