from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ActiveTimer(Base):
    __tablename__ = "active_timers"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_active_timers_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), index=True, nullable=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), index=True, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_type: Mapped[str] = mapped_column(String(30), nullable=False, default="professional_fee")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_seconds: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    case = relationship("Case")
    client = relationship("Client")
    user = relationship("User")
