"""
ALPHA Quant — Phase 5: Central Risk Gate.
Enforces institutional pre-trade risk controls, portfolio drawdown limits,
loss thresholds, data-freshness guards, and automated emergency halts.

Safety Invariant:
No strategy or client submission can bypass this gate.
All limits and calculations are documented with deterministic reset rules.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
import math

from app.models.paper import PaperAccount, PaperPosition, PaperRiskState
from app.paper.constants import (
    DEFAULT_MAX_ORDER_NOTIONAL,
    DEFAULT_MAX_POSITION_PCT,
    DEFAULT_MAX_PORTFOLIO_EXPOSURE_PCT,
    DEFAULT_DAILY_LOSS_LIMIT_PCT,
    DEFAULT_MAX_DRAWDOWN_LIMIT_PCT,
    DEFAULT_CONSECUTIVE_LOSS_LIMIT,
    DEFAULT_MAX_FEED_AGE_SECONDS,
    DEFAULT_MAX_SPREAD_BPS,
    MIN_ORDER_NOTIONAL_USD,
    OrderSide,
)
from app.paper.exceptions import (
    EmergencyStopActiveException,
    InvalidOrderException,
    LiveTradingForbiddenException,
    RiskBreachException,
    StaleFeedException,
)
from app.paper.schemas import PaperOrderCreateRequest


class CentralRiskGate:
    """
    Central Pre-Trade Risk Gate.
    Verifies all candidate orders prior to broker acceptance and execution.
    """

    def check_pre_trade_invariants(
        self,
        request: PaperOrderCreateRequest,
        account: PaperAccount,
        risk_state: PaperRiskState,
        current_position: Optional[PaperPosition],
        current_price: float,
        latest_feed_time: Optional[datetime] = None,
        spread_bps: Optional[float] = None,
    ) -> None:
        """
        Executes pre-trade risk verification pipeline in chronological order:
        1. Live execution safety invariant
        2. Emergency Stop / Kill switch
        3. Market data freshness
        4. Price & quantity mathematical validity
        5. Maximum order notional limit
        6. Maximum single position concentration limit
        7. Maximum aggregate portfolio exposure limit
        8. Daily loss threshold limit
        9. Peak-to-trough drawdown threshold limit
        10. Consecutive loss streak limit
        11. Bid-ask spread limit

        Raises a specific subclass of PaperExecutionException if any rule fails.
        """
        # 1. Live trading safety invariant
        if request.is_live:
            raise LiveTradingForbiddenException(
                "Live exchange execution is strictly forbidden. ALPHA Quant accepts simulated paper execution only."
            )

        # 2. Emergency Stop / Kill switch check
        if risk_state.emergency_stop:
            # We strictly block entries (BUY in long-only spot)
            if request.side == OrderSide.BUY:
                raise EmergencyStopActiveException(
                    f"Emergency Stop active: {risk_state.kill_switch_reason or 'Trading halted by risk officer'}."
                )

        # 3. Market data freshness check
        now_utc = datetime.now(timezone.utc)
        if latest_feed_time is not None:
            # Ensure feed time is timezone-aware
            if latest_feed_time.tzinfo is None:
                latest_feed_time = latest_feed_time.replace(tzinfo=timezone.utc)
            feed_age_seconds = (now_utc - latest_feed_time).total_seconds()
            if feed_age_seconds > DEFAULT_MAX_FEED_AGE_SECONDS:
                # Stale feed blocks entries
                if request.side == OrderSide.BUY:
                    raise StaleFeedException(
                        f"Market feed for {request.symbol} is stale ({feed_age_seconds:.1f}s old, max tolerated {DEFAULT_MAX_FEED_AGE_SECONDS}s). New entries blocked."
                    )

        # 4. Mathematical Price & Quantity validity check
        if request.quantity <= 0 or math.isnan(request.quantity) or math.isinf(request.quantity):
            raise InvalidOrderException(f"Invalid order quantity: {request.quantity}. Must be finite and positive.")

        ref_price = request.price if request.price is not None and request.price > 0 else current_price
        if ref_price <= 0 or math.isnan(ref_price) or math.isinf(ref_price):
            raise InvalidOrderException(f"Invalid reference price: {ref_price}. Must be finite and positive.")

        order_notional = request.quantity * ref_price
        if order_notional < MIN_ORDER_NOTIONAL_USD:
            raise InvalidOrderException(
                f"Order notional ${order_notional:.2f} is below minimum allowed ${MIN_ORDER_NOTIONAL_USD:.2f} USD."
            )

        # 5. Maximum order notional limit
        max_order_notional = risk_state.max_order_notional or DEFAULT_MAX_ORDER_NOTIONAL
        if order_notional > max_order_notional:
            raise RiskBreachException(
                rule_name="MAX_ORDER_NOTIONAL",
                message=f"Order notional ${order_notional:.2f} exceeds limit of ${max_order_notional:.2f}",
                current_value=order_notional,
                limit_value=max_order_notional,
            )

        # Compute Virtual Equity
        current_pos_qty = current_position.quantity if current_position else 0.0
        pos_market_val = current_pos_qty * current_price
        virtual_equity = account.virtual_balance + pos_market_val
        if virtual_equity <= 0:
            raise RiskBreachException(
                rule_name="NEGATIVE_EQUITY",
                message=f"Virtual equity is non-positive (${virtual_equity:.2f}). Trading halted.",
                current_value=virtual_equity,
                limit_value=0.0,
            )

        # 6. Maximum single position concentration limit (for BUY orders)
        if request.side == OrderSide.BUY:
            projected_qty = current_pos_qty + request.quantity
            projected_pos_notional = projected_qty * ref_price
            max_pos_pct = risk_state.max_position_pct or DEFAULT_MAX_POSITION_PCT
            max_allowed_pos_notional = virtual_equity * max_pos_pct

            if projected_pos_notional > max_allowed_pos_notional:
                raise RiskBreachException(
                    rule_name="MAX_POSITION_CONCENTRATION",
                    message=(
                        f"Projected position notional ${projected_pos_notional:.2f} ({projected_pos_notional/virtual_equity*100:.1f}%) "
                        f"exceeds maximum concentration limit of {max_pos_pct*100:.1f}% (${max_allowed_pos_notional:.2f})"
                    ),
                    current_value=projected_pos_notional,
                    limit_value=max_allowed_pos_notional,
                )

            # 7. Maximum aggregate portfolio exposure limit
            max_exp_pct = risk_state.max_portfolio_exposure_pct or DEFAULT_MAX_PORTFOLIO_EXPOSURE_PCT
            projected_total_exposure = pos_market_val + order_notional
            max_allowed_exposure = virtual_equity * max_exp_pct

            if projected_total_exposure > max_allowed_exposure:
                raise RiskBreachException(
                    rule_name="MAX_PORTFOLIO_EXPOSURE",
                    message=(
                        f"Projected aggregate portfolio exposure ${projected_total_exposure:.2f} "
                        f"({projected_total_exposure/virtual_equity*100:.1f}%) exceeds limit of {max_exp_pct*100:.1f}% (${max_allowed_exposure:.2f})"
                    ),
                    current_value=projected_total_exposure,
                    limit_value=max_allowed_exposure,
                )

        # 8. Daily loss threshold limit
        # Calculation: Daily loss is tracked relative to starting daily equity.
        # Reset behavior: Resets daily at 00:00 UTC or when elapsed time > 24 hours.
        self._check_and_update_daily_reset(risk_state, virtual_equity, now_utc)

        daily_loss_limit_pct = risk_state.daily_loss_limit_pct or DEFAULT_DAILY_LOSS_LIMIT_PCT
        starting_daily_equity = risk_state.starting_daily_equity or virtual_equity
        max_allowable_daily_loss = starting_daily_equity * daily_loss_limit_pct
        current_daily_pnl = risk_state.current_daily_pnl if risk_state.current_daily_pnl is not None else 0.0

        if current_daily_pnl < -1 * max_allowable_daily_loss:
            if request.side == OrderSide.BUY:
                # Auto-trip Emergency Stop
                risk_state.emergency_stop = True
                risk_state.kill_switch_reason = f"Daily loss limit breached: {current_daily_pnl:.2f} < -{max_allowable_daily_loss:.2f}"
                risk_state.last_breach_reason = risk_state.kill_switch_reason
                raise RiskBreachException(
                    rule_name="DAILY_LOSS_LIMIT",
                    message=f"Current daily loss ${abs(current_daily_pnl):.2f} exceeds allowable ${max_allowable_daily_loss:.2f} ({daily_loss_limit_pct*100:.1f}%)",
                    current_value=current_daily_pnl,
                    limit_value=-max_allowable_daily_loss,
                )

        # 9. Peak-to-trough drawdown threshold limit
        # Calculation: (peak_equity - current_equity) / peak_equity
        # Reset behavior: peak_equity updates upwards whenever new high watermark is achieved. Never resets downwards.
        peak_equity = risk_state.peak_equity if risk_state.peak_equity is not None else virtual_equity
        if virtual_equity > peak_equity:
            risk_state.peak_equity = virtual_equity
            peak_equity = virtual_equity

        if peak_equity > 0:
            current_dd_pct = (peak_equity - virtual_equity) / peak_equity
            max_dd_limit = risk_state.max_drawdown_limit_pct or DEFAULT_MAX_DRAWDOWN_LIMIT_PCT
            if current_dd_pct >= max_dd_limit:
                if request.side == OrderSide.BUY:
                    risk_state.emergency_stop = True
                    risk_state.kill_switch_reason = f"Drawdown limit breached: {current_dd_pct*100:.2f}% >= {max_dd_limit*100:.2f}%"
                    risk_state.last_breach_reason = risk_state.kill_switch_reason
                    raise RiskBreachException(
                        rule_name="MAX_DRAWDOWN_LIMIT",
                        message=f"Current portfolio drawdown {current_dd_pct*100:.2f}% exceeds maximum allowable {max_dd_limit*100:.2f}%",
                        current_value=current_dd_pct,
                        limit_value=max_dd_limit,
                    )

        # 10. Consecutive loss streak limit
        # Calculation: Count of sequential losing closed trades.
        # Reset behavior: Resets to 0 immediately upon a profitable trade (realized PnL > 0) or explicit admin reset.
        consecutive_losses = risk_state.consecutive_losses if risk_state.consecutive_losses is not None else 0
        consecutive_limit = risk_state.consecutive_loss_limit or DEFAULT_CONSECUTIVE_LOSS_LIMIT
        if consecutive_losses >= consecutive_limit:
            if request.side == OrderSide.BUY:
                raise RiskBreachException(
                    rule_name="CONSECUTIVE_LOSS_LIMIT",
                    message=f"Account has suffered {consecutive_losses} consecutive loss trades (limit: {consecutive_limit}). New entries blocked.",
                    current_value=consecutive_losses,
                    limit_value=consecutive_limit,
                )

        # 11. Spread filter
        if spread_bps is not None and spread_bps > DEFAULT_MAX_SPREAD_BPS:
            if request.side == OrderSide.BUY:
                raise RiskBreachException(
                    rule_name="EXCESSIVE_SPREAD",
                    message=f"Bid-ask spread {spread_bps:.1f} bps exceeds limit {DEFAULT_MAX_SPREAD_BPS:.1f} bps.",
                    current_value=spread_bps,
                    limit_value=DEFAULT_MAX_SPREAD_BPS,
                )

    def _check_and_update_daily_reset(
        self,
        risk_state: PaperRiskState,
        current_equity: float,
        now_utc: datetime,
    ) -> None:
        """
        Determines if a daily boundary has passed. If so, rolls starting_daily_equity
        and resets current_daily_pnl.
        """
        last_reset = risk_state.last_daily_reset
        if last_reset is None:
            risk_state.last_daily_reset = now_utc
            risk_state.starting_daily_equity = current_equity
            risk_state.current_daily_pnl = 0.0
            return

        if last_reset.tzinfo is None:
            last_reset = last_reset.replace(tzinfo=timezone.utc)

        # If day has changed or > 24 hours elapsed
        if now_utc.date() > last_reset.date() or (now_utc - last_reset).total_seconds() >= 86400:
            risk_state.starting_daily_equity = current_equity
            risk_state.current_daily_pnl = 0.0
            risk_state.last_daily_reset = now_utc

