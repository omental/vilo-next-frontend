from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OperatingTransaction(Base):
    __tablename__ = "operating_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    operating_account_id: Mapped[int] = mapped_column(ForeignKey("operating_accounts.id", ondelete="CASCADE"), index=True, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), index=True, nullable=True)
    linked_trust_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("trust_transactions.id", ondelete="SET NULL"), index=True, nullable=True)
    linked_payment_id: Mapped[int | None] = mapped_column(ForeignKey("invoice_payments.id", ondelete="SET NULL"), index=True, nullable=True)
    linked_expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id", ondelete="SET NULL"), index=True, nullable=True)
    reversal_of_id: Mapped[int | None] = mapped_column(ForeignKey("operating_transactions.id", ondelete="SET NULL"), index=True, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization = relationship("Organization", back_populates="operating_transactions")
    operating_account = relationship("OperatingAccount", back_populates="transactions")
    invoice = relationship("Invoice", back_populates="operating_transactions")
    trust_transaction = relationship("TrustTransaction")
    expense = relationship("Expense", back_populates="operating_transactions")
    creator = relationship("User", foreign_keys=[created_by_id], back_populates="created_operating_transactions")
    voided_by = relationship("User", foreign_keys=[voided_by_id], back_populates="voided_operating_transactions")
    invoice_payments = relationship("InvoicePayment", foreign_keys="InvoicePayment.linked_operating_transaction_id", back_populates="operating_transaction")
    linked_payment = relationship("InvoicePayment", foreign_keys=[linked_payment_id], back_populates="operating_links")
    reversal_of = relationship("OperatingTransaction", remote_side=[id], foreign_keys=[reversal_of_id], back_populates="reversal_transactions")
    reversal_transactions = relationship("OperatingTransaction", foreign_keys=[reversal_of_id], back_populates="reversal_of")
