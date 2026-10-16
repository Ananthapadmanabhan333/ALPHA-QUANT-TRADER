"""
ALPHA Quant — Phase 5: Paper Trading & Risk Operations CLI.
Inspect account balances, positions, pre-trade risk controls, submit orders, and emergency halt.
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import close_database_connection, get_session_factory
from app.paper.constants import OrderSide, OrderType
from app.paper.schemas import EmergencyResumeRequest, EmergencyStopRequest, PaperOrderCreateRequest
from app.paper.service import PaperService


async def main():
    parser = argparse.ArgumentParser(
        description="ALPHA Quant — Paper Execution & Central Risk Operations CLI"
    )
    parser.add_argument(
        "--action",
        type=str,
        default="status",
        choices=["status", "order", "cancel", "emergency-stop", "resume", "reconcile"],
        help="Action to perform",
    )
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading pair symbol")
    parser.add_argument("--side", type=str, choices=["buy", "sell"], help="Order side (for action=order)")
    parser.add_argument("--type", type=str, default="market", choices=["market", "limit"], help="Order type")
    parser.add_argument("--quantity", type=float, help="Order quantity in base asset")
    parser.add_argument("--price", type=float, help="Limit price (for limit order or reference)")
    parser.add_argument("--client-order-id", type=str, help="Custom client order ID for idempotency")
    parser.add_argument("--order-id", type=str, help="Order ID to cancel (for action=cancel)")
    parser.add_argument("--reason", type=str, default="Manual CLI emergency pause", help="Emergency stop reason")
    parser.add_argument("--confirmation", type=str, help="Confirmation token for resume ('CONFIRM_RESUME')")
    parser.add_argument("--output-json", type=str, help="Path to write JSON response")

    args = parser.parse_args()

    session_factory = get_session_factory()
    service = PaperService()

    print("=" * 70)
    print("ALPHA QUANT — PAPER EXECUTION & RISK OPERATIONS")
    print("=" * 70)

    try:
        async with session_factory() as db:
            if args.action == "status":
                account = await service.get_account_overview(db, symbol=args.symbol)
                risk = await service.get_risk_status(db, symbol=args.symbol)

                print(f"Account:         {account.name} ({account.account_id})")
                print(f"Virtual Cash:    ${account.virtual_balance:,.2f} {account.currency}")
                print(f"Total Equity:    ${account.total_equity:,.2f} {account.currency}")
                print(f"Realized P&L:    ${account.realized_pnl:+,.2f}")
                print(f"Unrealized P&L:  ${account.unrealized_pnl:+,.2f}")
                print("-" * 70)
                print("RISK GATE STATUS:")
                print(f"  Emergency Stop:    {'[HALTED]' if risk.emergency_stop else '[ACTIVE/NORMAL]'}")
                if risk.emergency_stop:
                    print(f"  Halt Reason:       {risk.kill_switch_reason}")
                print(f"  Feed Status:       {risk.feed_status}")
                print(f"  Trading Allowed:   {risk.is_trading_allowed}")
                print(f"  Current Drawdown:  {risk.current_drawdown_pct:.2f}% (Limit: {risk.max_drawdown_limit_pct:.1f}%)")
                print(f"  Daily P&L:         ${risk.current_daily_pnl:+,.2f} (Limit: {risk.daily_loss_limit_pct:.1f}%)")
                print(f"  Loss Streak:       {risk.consecutive_losses} consecutive (Limit: {risk.consecutive_loss_limit})")
                print("-" * 70)
                print(f"OPEN POSITIONS ({len(account.positions)}):")
                if not account.positions:
                    print("  No open spot positions.")
                else:
                    for p in account.positions:
                        print(
                            f"  {p.symbol}: {p.quantity:.4f} @ ${p.avg_entry_price:,.2f} | "
                            f"Value: ${p.market_value:,.2f} | Unr PnL: ${p.unrealized_pnl:+,.2f} ({p.unrealized_pnl_pct:+.2f}%)"
                        )

                if args.output_json:
                    out = {"account": account.model_dump(), "risk": risk.model_dump()}
                    Path(args.output_json).write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
                    print(f"\nSaved status report to: {args.output_json}")

            elif args.action == "order":
                if not args.side or not args.quantity:
                    print("ERROR: action=order requires --side and --quantity")
                    sys.exit(1)

                req = PaperOrderCreateRequest(
                    symbol=args.symbol,
                    side=OrderSide(args.side),
                    order_type=OrderType(args.type),
                    quantity=args.quantity,
                    price=args.price,
                    client_order_id=args.client_order_id,
                    current_market_price=args.price,
                )
                order = await service.submit_paper_order(db, req)
                print(f"ORDER SUBMISSION RESULT:")
                print(f"  Order ID:        {order.id}")
                print(f"  Client Order ID: {order.client_order_id}")
                print(f"  Status:          {order.status.upper()}")
                print(f"  Side/Type:       {order.side.upper()} {order.order_type.upper()}")
                print(f"  Quantity:        {order.quantity:.4f} {order.symbol}")
                if order.avg_fill_price:
                    print(f"  Fill Price:      ${order.avg_fill_price:,.2f}")
                    print(f"  Fee Paid:        ${order.fee:.4f}")
                    print(f"  Slippage Cost:   ${order.slippage_cost:.4f}")
                if order.rejection_reason:
                    print(f"  Rejection:       {order.rejection_reason}")

            elif args.action == "cancel":
                if not args.order_id:
                    print("ERROR: action=cancel requires --order-id")
                    sys.exit(1)
                order = await service.cancel_paper_order(db, args.order_id)
                print(f"Order {order.id} status: {order.status.upper()}")

            elif args.action == "emergency-stop":
                risk = await service.trigger_emergency_stop(db, args.reason)
                print(f"EMERGENCY STOP TRIGGERED: {risk.kill_switch_reason}")
                print(f"Trading Allowed: {risk.is_trading_allowed}")

            elif args.action == "resume":
                token = args.confirmation or "CONFIRM_RESUME"
                risk = await service.resume_emergency_stop(db, confirmation=token, reset_consecutive_losses=True)
                print("EMERGENCY STOP CLEARED. Risk controls active.")
                print(f"Trading Allowed: {risk.is_trading_allowed}")

            elif args.action == "reconcile":
                candle = await service.get_latest_market_candle(db, symbol=args.symbol)
                price = candle.close if candle else 50000.0
                rec = await service.broker.reconcile_portfolio(db, current_market_price=price, symbol=args.symbol)
                print("PORTFOLIO RECONCILIATION RESULT:")
                for k, v in rec.items():
                    print(f"  {k:22}: {v}")

    except Exception as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)
    finally:
        await close_database_connection()


if __name__ == "__main__":
    asyncio.run(main())
