"""
SQLAlchemy models for ALPHA Quant Phase 5 Paper Execution & Risk Subsystem.
Stores virtual accounts, orders, fills, positions, and risk states with full transactional integrity.
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class PaperAccount(Base):
    """
    Virtual trading account isolated to paper simulation.
    Safety Invariant: Strictly prohibited from holding live exchange credentials.
    """
    __tablename__ = "paper_accounts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(50), nullable=False, default="Default Paper Account")
    virtual_balance = Column(Float, nullable=False, default=10000.0)  # USDT Cash
    currency = Column(String(10), nullable=False, default="USDT")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    orders = relationship("PaperOrder", back_populates="account", cascade="all, delete-orphan")
    fills = relationship("PaperFill", back_populates="account", cascade="all, delete-orphan")
    positions = relationship("PaperPosition", back_populates="account", cascade="all, delete-orphan")
    risk_state = relationship("PaperRiskState", back_populates="account", uselist=False, cascade="all, delete-orphan")
    risk_events = relationship("PaperRiskEvent", back_populates="account", cascade="all, delete-orphan")


class PaperOrder(Base):
    """
    Simulated order submitted to the PaperBroker.
    Enforces idempotency via unique client_order_id.
    """
    __tablename__ = "paper_orders"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    client_order_id = Column(String(64), nullable=False, unique=True, index=True)
    account_id = Column(String(36), ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # buy, sell
    order_type = Column(String(10), nullable=False)  # market, limit
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=True)  # Null for market orders
    filled_quantity = Column(Float, nullable=False, default=0.0)
    avg_fill_price = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending, open, filled, partially_filled, cancelled, rejected
    fee = Column(Float, nullable=False, default=0.0)
    slippage_cost = Column(Float, nullable=False, default=0.0)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    account = relationship("PaperAccount", back_populates="orders")
    fills = relationship("PaperFill", back_populates="order", cascade="all, delete-orphan")


class PaperFill(Base):
    """
    Atomic execution fill record resulting from an order match.
    """
    __tablename__ = "paper_fills"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_id = Column(String(36), ForeignKey("paper_orders.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(String(36), ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # buy, sell
    fill_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    gross_notional = Column(Float, nullable=False)
    fee = Column(Float, nullable=False, default=0.0)
    slippage_cost = Column(Float, nullable=False, default=0.0)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    order = relationship("PaperOrder", back_populates="fills")
    account = relationship("PaperAccount", back_populates="fills")


class PaperPosition(Base):
    """
    Aggregate spot inventory position tracked with weighted-average cost accounting.
    """
    __tablename__ = "paper_positions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    account_id = Column(String(36), ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False, default=0.0)
    avg_entry_price = Column(Float, nullable=False, default=0.0)
    cost_basis = Column(Float, nullable=False, default=0.0)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("account_id", "symbol", name="uq_paper_positions_account_symbol"),
    )

    account = relationship("PaperAccount", back_populates="positions")


class PaperRiskState(Base):
    """
    Persisted risk state and parameters for the Central Risk Gate.
    Safety Invariant: Risk limits are never silently reset after restart.
    """
    __tablename__ = "paper_risk_state"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    account_id = Column(String(36), ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False, unique=True)
    emergency_stop = Column(Boolean, nullable=False, default=False)
    kill_switch_reason = Column(Text, nullable=True)
    max_order_notional = Column(Float, nullable=False, default=10000.0)
    max_position_pct = Column(Float, nullable=False, default=0.10)
    max_portfolio_exposure_pct = Column(Float, nullable=False, default=0.80)
    daily_loss_limit_pct = Column(Float, nullable=False, default=0.02)
    max_drawdown_limit_pct = Column(Float, nullable=False, default=0.05)
    consecutive_loss_limit = Column(Integer, nullable=False, default=3)
    starting_daily_equity = Column(Float, nullable=False, default=10000.0)
    current_daily_pnl = Column(Float, nullable=False, default=0.0)
    peak_equity = Column(Float, nullable=False, default=10000.0)
    consecutive_losses = Column(Integer, nullable=False, default=0)
    last_daily_reset = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_breach_reason = Column(Text, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    account = relationship("PaperAccount", back_populates="risk_state")


class PaperRiskEvent(Base):
    """
    Immutable audit log for risk limit breaches, emergency pauses, and reconciliation alerts.
    """
    __tablename__ = "paper_risk_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    account_id = Column(String(36), ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False, default="WARNING")
    reason = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    account = relationship("PaperAccount", back_populates="risk_events")


# Indexes for efficient audit queries
Index("ix_paper_orders_account_created", PaperOrder.account_id, PaperOrder.created_at)
Index("ix_paper_fills_account_created", PaperFill.account_id, PaperFill.created_at)
Index("ix_paper_risk_events_account_created", PaperRiskEvent.account_id, PaperRiskEvent.created_at)
