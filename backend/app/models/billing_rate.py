from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BillingRate(Base):
    __tablename__ = "billing_rates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    rate_type: Mapped[str] = mapped_column(String(30), nullable=False)
    role_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    organization = relationship("Organization", back_populates="billing_rates")
    user = relationship("User", foreign_keys=[user_id], back_populates="billing_rates")
    creator = relationship("User", foreign_keys=[created_by_id], back_populates="created_billing_rates")
