from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FirmPaymentAccount(Base):
    __tablename__ = "firm_payment_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_number: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    swift_routing: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    organization = relationship("Organization", back_populates="firm_payment_accounts")
    creator = relationship("User", back_populates="created_firm_payment_accounts")
    invoices = relationship("Invoice", back_populates="payment_account")
