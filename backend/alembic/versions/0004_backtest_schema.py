"""Create backtest_runs and backtest_trades tables

Revision ID: 0004_backtest_schema
Revises: 0003_strategy_experiments_schema
Create Date: 2026-10-17 00:36:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_backtest_schema"
down_revision: Union[str, None] = "0003_strategy_experiments_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. backtest_runs table
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("strategy_id", sa.String(length=50), nullable=False),
        sa.Column("strategy_version", sa.String(length=20), nullable=False),
        sa.Column("config_id", sa.String(length=20), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("interval", sa.String(length=10), nullable=False),
        sa.Column("time_range_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_range_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("candle_count", sa.Integer(), nullable=False),
        sa.Column("dataset_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("cost_assumptions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("equity_curve", sa.JSON(), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("net_return_pct", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("sharpe_ratio", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("max_drawdown_pct", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("profit_factor", sa.Float(), nullable=True),
        sa.Column("win_rate_pct", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_backtest_runs_lookup",
        "backtest_runs",
        ["strategy_id", "symbol", "created_at"],
    )
    op.create_index(
        "ix_backtest_runs_fingerprint",
        "backtest_runs",
        ["dataset_fingerprint"],
    )
    op.create_index(
        "ix_backtest_runs_status",
        "backtest_runs",
        ["status"],
    )

    # 2. backtest_trades table
    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("backtest_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fill_price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("gross_notional", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False),
        sa.Column("slippage_cost", sa.Float(), nullable=False),
        sa.Column("realized_net_pnl", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_backtest_trades_run_ts",
        "backtest_trades",
        ["backtest_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_table("backtest_trades")
    op.drop_table("backtest_runs")
