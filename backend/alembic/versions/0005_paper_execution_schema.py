"""Create paper trading and risk management schema

Revision ID: 0005_paper_execution_schema
Revises: 0004_backtest_schema
Create Date: 2026-10-17 00:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005_paper_execution_schema"
down_revision: Union[str, None] = "0004_backtest_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. paper_accounts table
    op.create_table(
        "paper_accounts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False, server_default="Default Paper Account"),
        sa.Column("virtual_balance", sa.Float(), nullable=False, server_default="10000.0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USDT"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 2. paper_orders table
    op.create_table(
        "paper_orders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("client_order_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column(
            "account_id",
            sa.String(length=36),
            sa.ForeignKey("paper_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("order_type", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("filled_quantity", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("avg_fill_price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("fee", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("slippage_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_paper_orders_account_created",
        "paper_orders",
        ["account_id", "created_at"],
    )

    # 3. paper_fills table
    op.create_table(
        "paper_fills",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "order_id",
            sa.String(length=36),
            sa.ForeignKey("paper_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.String(length=36),
            sa.ForeignKey("paper_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("fill_price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("gross_notional", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("slippage_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_paper_fills_account_created",
        "paper_fills",
        ["account_id", "created_at"],
    )

    # 4. paper_positions table
    op.create_table(
        "paper_positions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(length=36),
            sa.ForeignKey("paper_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("avg_entry_price", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("cost_basis", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("account_id", "symbol", name="uq_paper_positions_account_symbol"),
    )

    # 5. paper_risk_state table
    op.create_table(
        "paper_risk_state",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(length=36),
            sa.ForeignKey("paper_accounts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("emergency_stop", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("kill_switch_reason", sa.Text(), nullable=True),
        sa.Column("max_order_notional", sa.Float(), nullable=False, server_default="10000.0"),
        sa.Column("max_position_pct", sa.Float(), nullable=False, server_default="0.10"),
        sa.Column("max_portfolio_exposure_pct", sa.Float(), nullable=False, server_default="0.80"),
        sa.Column("daily_loss_limit_pct", sa.Float(), nullable=False, server_default="0.02"),
        sa.Column("max_drawdown_limit_pct", sa.Float(), nullable=False, server_default="0.05"),
        sa.Column("consecutive_loss_limit", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("starting_daily_equity", sa.Float(), nullable=False, server_default="10000.0"),
        sa.Column("current_daily_pnl", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("peak_equity", sa.Float(), nullable=False, server_default="10000.0"),
        sa.Column("consecutive_losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_daily_reset",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_breach_reason", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 6. paper_risk_events table
    op.create_table(
        "paper_risk_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(length=36),
            sa.ForeignKey("paper_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="WARNING"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_paper_risk_events_account_created",
        "paper_risk_events",
        ["account_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("paper_risk_events")
    op.drop_table("paper_risk_state")
    op.drop_table("paper_positions")
    op.drop_table("paper_fills")
    op.drop_table("paper_orders")
    op.drop_table("paper_accounts")
