from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_source: Mapped[str] = mapped_column(String(20), nullable=False)
    paid_at: Mapped[date] = mapped_column(Date, nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_trust_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("trust_transactions.id", ondelete="SET NULL"), index=True, nullable=True)
    linked_operating_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("operating_transactions.id", ondelete="SET NULL"), index=True, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization = relationship("Organization", back_populates="invoice_payments")
    invoice = relationship("Invoice", back_populates="payments")
    trust_transaction = relationship("TrustTransaction", back_populates="invoice_payments")
    operating_transaction = relationship("OperatingTransaction", foreign_keys=[linked_operating_transaction_id], back_populates="invoice_payments")
    operating_links = relationship("OperatingTransaction", foreign_keys="OperatingTransaction.linked_payment_id", back_populates="linked_payment")
    created_by = relationship("User", foreign_keys=[created_by_id], back_populates="created_invoice_payments")
    voided_by = relationship("User", foreign_keys=[voided_by_id], back_populates="voided_invoice_payments")
