from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TrustAccount(Base):
    __tablename__ = "trust_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="JMD")
    account_type: Mapped[str] = mapped_column(String(30), nullable=False, default="pooled")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_number_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    organization = relationship("Organization", back_populates="trust_accounts")
    ledgers = relationship("TrustLedger", back_populates="trust_account", cascade="all, delete-orphan")
    transactions = relationship("TrustTransaction", back_populates="trust_account", cascade="all, delete-orphan")
    reconciliations = relationship("TrustReconciliation", back_populates="trust_account", cascade="all, delete-orphan")
