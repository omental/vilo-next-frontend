from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id_is_read", "user_id", "is_read"),
        Index(
            "ix_notifications_pending_popup", "organization_id", "user_id", "popup_dismissed_at", "created_at",
            postgresql_where=text("popup_dismissed_at IS NULL AND type IN ('task_reminder','task_due','task_overdue','event_reminder','event_due')"),
        ),
        Index(
            "ix_notifications_email_delivery", "email_status", "email_last_attempt_at",
            postgresql_where=text("email_status IS NOT NULL"),
        ),
        UniqueConstraint("organization_id", "user_id", "dedupe_key", name="uq_notifications_org_user_dedupe"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    popup_dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    email_last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    organization = relationship("Organization", back_populates="notifications")
    user = relationship("User", back_populates="notifications")
