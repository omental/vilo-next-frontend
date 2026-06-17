from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TrustReconciliation(Base):
    __tablename__ = "trust_reconciliations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    trust_account_id: Mapped[int] = mapped_column(ForeignKey("trust_accounts.id", ondelete="CASCADE"), index=True, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    bank_statement_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    ledger_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    client_ledger_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    matter_ledger_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    difference: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    prepared_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization = relationship("Organization", back_populates="trust_reconciliations")
    trust_account = relationship("TrustAccount", back_populates="reconciliations")
    prepared_by = relationship("User", back_populates="prepared_trust_reconciliations")
