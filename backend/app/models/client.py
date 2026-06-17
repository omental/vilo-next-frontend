from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_type: Mapped[str] = mapped_column(String(50), nullable=False, default="individual")
    trn_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_contact_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    billing_currency: Mapped[str | None] = mapped_column(String(10), nullable=True, default="USD")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    organization = relationship("Organization", back_populates="clients")
    user = relationship("User", back_populates="client_profile")
    cases = relationship("Case", back_populates="client", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="client")
    invoices = relationship("Invoice", back_populates="client")
    trust_ledgers = relationship("TrustLedger", back_populates="client")
    trust_transactions = relationship("TrustTransaction", back_populates="client")
    trust_receipts = relationship("TrustReceipt", back_populates="client")
    intakes = relationship("ClientIntake", back_populates="client", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="client")
    assignments = relationship("ClientAssignment", back_populates="client", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="client")


class ClientAssignment(Base):
    __tablename__ = "client_assignments"
    __table_args__ = (UniqueConstraint("client_id", "user_id", name="uq_client_assignments_client_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    client = relationship("Client", back_populates="assignments")
    user = relationship("User", back_populates="client_assignments")
