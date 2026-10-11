"""Create market_candles table with TimescaleDB compatibility

Revision ID: 0002_market_candles_schema
Revises: 0001_initial_schema
Create Date: 2026-10-11 12:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_market_candles_schema"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_candles",
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("interval", sa.String(length=10), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("high", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("low", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("close", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("volume", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("quote_volume", sa.Numeric(precision=24, scale=8), nullable=False, server_default="0"),
        sa.Column("trades_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("taker_buy_base_volume", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("taker_buy_quote_volume", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="binance_spot"),
        sa.Column("exchange_event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("symbol", "interval", "open_time", name="pk_market_candles"),
    )

    op.create_index(
        "ix_market_candles_symbol",
        "market_candles",
        ["symbol"],
        unique=False,
    )
    op.create_index(
        "ix_market_candles_interval",
        "market_candles",
        ["interval"],
        unique=False,
    )
    op.create_index(
        "ix_market_candles_open_time",
        "market_candles",
        ["open_time"],
        unique=False,
    )
    op.create_index(
        "ix_market_candles_is_closed",
        "market_candles",
        ["is_closed"],
        unique=False,
    )
    op.create_index(
        "ix_market_candles_query",
        "market_candles",
        ["symbol", "interval", "is_closed", "open_time"],
        unique=False,
    )

    # Enable TimescaleDB hypertable if timescaledb extension is available
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        try:
            conn.execute(
                sa.text(
                    "DO $$ "
                    "BEGIN "
                    "  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN "
                    "    PERFORM create_hypertable('market_candles', 'open_time', if_not_exists => TRUE); "
                    "  END IF; "
                    "END $$;"
                )
            )
        except Exception:
            pass


def downgrade() -> None:
    op.drop_index("ix_market_candles_query", table_name="market_candles")
    op.drop_index("ix_market_candles_is_closed", table_name="market_candles")
    op.drop_index("ix_market_candles_open_time", table_name="market_candles")
    op.drop_index("ix_market_candles_interval", table_name="market_candles")
    op.drop_index("ix_market_candles_symbol", table_name="market_candles")
    op.drop_table("market_candles")
