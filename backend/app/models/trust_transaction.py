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
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="RESTRICT"), index=True, nullable=True)
    linked_invoice_id: Mapped[int | None] = mapped_column("invoice_id", ForeignKey("invoices.id", ondelete="SET NULL"), index=True, nullable=True)
    transaction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payee_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payee_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    adjustment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    adjustment_direction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reversal_of_id: Mapped[int | None] = mapped_column(ForeignKey("trust_transactions.id", ondelete="SET NULL"), index=True, nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by_id: Mapped[int] = mapped_column("created_by", ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization = relationship("Organization", back_populates="trust_transactions")
    trust_account = relationship("TrustAccount", back_populates="transactions")
    ledger = relationship("TrustLedger", back_populates="transactions")
    client = relationship("Client", back_populates="trust_transactions")
    case = relationship("Case", back_populates="trust_transactions")
    invoice = relationship("Invoice", back_populates="trust_transactions")
    creator = relationship("User", foreign_keys=[created_by_id], back_populates="trust_transactions")
    voided_by = relationship("User", foreign_keys=[voided_by_id], back_populates="voided_trust_transactions")
    receipt = relationship("TrustReceipt", back_populates="trust_transaction", uselist=False, cascade="all, delete-orphan")
    reversal_of = relationship("TrustTransaction", remote_side=[id], foreign_keys=[reversal_of_id], back_populates="reversal_transactions")
    reversal_transactions = relationship("TrustTransaction", back_populates="reversal_of")
    invoice_payments = relationship("InvoicePayment", back_populates="trust_transaction")
