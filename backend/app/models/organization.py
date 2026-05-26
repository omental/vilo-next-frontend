from datetime import datetime
from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RecordStatus


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    status: Mapped[RecordStatus] = mapped_column(Enum(RecordStatus), default=RecordStatus.active, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    users = relationship("User", back_populates="organization")
    clients = relationship("Client", back_populates="organization", cascade="all, delete-orphan")
    cases = relationship("Case", back_populates="organization", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="organization", cascade="all, delete-orphan")
    calendar_events = relationship("CalendarEvent", back_populates="organization", cascade="all, delete-orphan")
    timeline_events = relationship("CaseTimelineEvent", back_populates="organization", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="organization", cascade="all, delete-orphan")
    case_notes = relationship("CaseNote", back_populates="organization", cascade="all, delete-orphan")
    time_entries = relationship("TimeEntry", back_populates="organization", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="organization", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="organization", cascade="all, delete-orphan")
    invoice_line_items = relationship("InvoiceLineItem", back_populates="organization", cascade="all, delete-orphan")
    trust_accounts = relationship("TrustAccount", back_populates="organization", cascade="all, delete-orphan")
    trust_ledgers = relationship("TrustLedger", back_populates="organization", cascade="all, delete-orphan")
    trust_transactions = relationship("TrustTransaction", back_populates="organization", cascade="all, delete-orphan")
    client_intakes = relationship("ClientIntake", back_populates="organization", cascade="all, delete-orphan")

    conversations = relationship("Conversation", back_populates="organization", cascade="all, delete-orphan")
    conversation_participants = relationship("ConversationParticipant", back_populates="organization", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="organization", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="organization", cascade="all, delete-orphan")

    user_invites = relationship("UserInvite", back_populates="organization", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="organization", cascade="all, delete-orphan")
