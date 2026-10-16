"""Create strategy_experiments and strategy_signals tables

Revision ID: 0003_strategy_experiments_schema
Revises: 0002_market_candles_schema
Create Date: 2026-10-11 14:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_strategy_experiments_schema"
down_revision: Union[str, None] = "0002_market_candles_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. strategy_experiments table
    op.create_table(
        "strategy_experiments",
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
        sa.Column("feature_definitions", sa.JSON(), nullable=False),
        sa.Column("signal_timestamps", sa.JSON(), nullable=False),
        sa.Column("total_signals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("buy_signals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sell_signals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hold_signals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_strategy_experiments_lookup",
        "strategy_experiments",
        ["strategy_id", "symbol", "created_at"],
    )
    op.create_index(
        "ix_strategy_experiments_config",
        "strategy_experiments",
        ["config_id"],
    )
    op.create_index(
        "ix_strategy_experiments_fingerprint",
        "strategy_experiments",
        ["dataset_fingerprint"],
    )

    # 2. strategy_signals table
    op.create_table(
        "strategy_signals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("experiment_id", sa.String(length=36), nullable=False),
        sa.Column("strategy_id", sa.String(length=50), nullable=False),
        sa.Column("strategy_version", sa.String(length=20), nullable=False),
        sa.Column("config_id", sa.String(length=20), nullable=False),
        sa.Column("decision_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("signal_score", sa.Float(), nullable=False),
        sa.Column("reference_price", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("relevant_features", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_strategy_signals_exp_ts",
        "strategy_signals",
        ["experiment_id", "decision_timestamp"],
    )
    op.create_index(
        "ix_strategy_signals_query",
        "strategy_signals",
        ["strategy_id", "symbol", "decision_timestamp"],
    )


def downgrade() -> None:
    op.drop_table("strategy_signals")
    op.drop_table("strategy_experiments")
