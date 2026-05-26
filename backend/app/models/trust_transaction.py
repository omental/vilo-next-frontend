from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TrustTransaction(Base):
    __tablename__ = "trust_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    trust_account_id: Mapped[int] = mapped_column(ForeignKey("trust_accounts.id", ondelete="CASCADE"), index=True, nullable=False)
    ledger_id: Mapped[int] = mapped_column(ForeignKey("trust_ledgers.id", ondelete="CASCADE"), index=True, nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), index=True, nullable=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), index=True, nullable=True)
    transaction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    organization = relationship("Organization", back_populates="trust_transactions")
    trust_account = relationship("TrustAccount", back_populates="transactions")
    ledger = relationship("TrustLedger", back_populates="transactions")
    client = relationship("Client", back_populates="trust_transactions")
    case = relationship("Case", back_populates="trust_transactions")
    invoice = relationship("Invoice", back_populates="trust_transactions")
    creator = relationship("User", back_populates="trust_transactions")
