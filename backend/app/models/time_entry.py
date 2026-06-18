from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), index=True, nullable=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), index=True, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), index=True, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    billing_type: Mapped[str] = mapped_column(String(30), nullable=False, default="professional_fee")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    rate_is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="billable")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    organization = relationship("Organization", back_populates="time_entries")
    case = relationship("Case", back_populates="time_entries")
    client = relationship("Client")
    user = relationship("User", back_populates="time_entries")
    invoice = relationship("Invoice")
    invoice_line_items = relationship("InvoiceLineItem", back_populates="time_entry")
