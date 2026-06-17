from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TrustReceipt(Base):
    __tablename__ = "trust_receipts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    trust_transaction_id: Mapped[int] = mapped_column(ForeignKey("trust_transactions.id", ondelete="CASCADE"), index=True, nullable=False, unique=True)
    receipt_number: Mapped[str] = mapped_column(String(50), nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="RESTRICT"), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization = relationship("Organization", back_populates="trust_receipts")
    trust_transaction = relationship("TrustTransaction", back_populates="receipt")
    client = relationship("Client", back_populates="trust_receipts")
    case = relationship("Case", back_populates="trust_receipts")
    issued_by = relationship("User", foreign_keys=[issued_by_id], back_populates="issued_trust_receipts")
    voided_by = relationship("User", foreign_keys=[voided_by_id], back_populates="voided_trust_receipts")
