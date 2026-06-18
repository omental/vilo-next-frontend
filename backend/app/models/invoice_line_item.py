from datetime import datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"
    __table_args__ = (
        CheckConstraint(
            "line_type NOT IN ('trust_deposit', 'retainer_deposit', 'escrow', 'client_funds', 'property_funds', 'trust_income', 'trust_revenue', 'invoice_retainer')",
            name="ck_invoice_line_items_no_trust_categories",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False)
    line_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    hours: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    time_entry_id: Mapped[int | None] = mapped_column(ForeignKey("time_entries.id", ondelete="SET NULL"), nullable=True, index=True)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True, index=True)
    staff_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    organization = relationship("Organization", back_populates="invoice_line_items")
    invoice = relationship("Invoice", back_populates="line_items")
    time_entry = relationship("TimeEntry", back_populates="invoice_line_items")
    expense = relationship("Expense", back_populates="invoice_line_items")
    staff_user = relationship("User", back_populates="invoice_line_items")
