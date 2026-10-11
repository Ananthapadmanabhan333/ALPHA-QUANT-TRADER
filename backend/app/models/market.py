from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Index,
    PrimaryKeyConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class MarketCandle(Base):
    """
    TimescaleDB hypertable compatible OHLCV candle record.
    Stores exchange timestamps and ingestion timestamps separately in UTC.
    Distinguishes open/in-progress candles from finalized candles via `is_closed`.
    """
    __tablename__ = "market_candles"

    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    interval: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    open: Mapped[float] = mapped_column(Numeric(18, 8, asdecimal=False), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(18, 8, asdecimal=False), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(18, 8, asdecimal=False), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(18, 8, asdecimal=False), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(24, 8, asdecimal=False), nullable=False)
    quote_volume: Mapped[float] = mapped_column(Numeric(24, 8, asdecimal=False), nullable=False, default=0.0)

    trades_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    taker_buy_base_volume: Mapped[float | None] = mapped_column(Numeric(24, 8, asdecimal=False), nullable=True)
    taker_buy_quote_volume: Mapped[float | None] = mapped_column(Numeric(24, 8, asdecimal=False), nullable=True)

    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="binance_spot")
    exchange_event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        PrimaryKeyConstraint("symbol", "interval", "open_time", name="pk_market_candles"),
        Index("ix_market_candles_query", "symbol", "interval", "is_closed", "open_time"),
    )

    def __repr__(self) -> str:
        return (
            f"<MarketCandle(symbol='{self.symbol}', interval='{self.interval}', "
            f"open_time='{self.open_time}', close={self.close}, is_closed={self.is_closed})>"
        )
