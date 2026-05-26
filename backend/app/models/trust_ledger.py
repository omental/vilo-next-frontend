from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TrustLedger(Base):
    __tablename__ = "trust_ledgers"
    __table_args__ = (UniqueConstraint("trust_account_id", "client_id", "case_id", name="uq_trust_ledger_account_client_case"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    trust_account_id: Mapped[int] = mapped_column(ForeignKey("trust_accounts.id", ondelete="CASCADE"), index=True, nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), index=True, nullable=True)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    organization = relationship("Organization", back_populates="trust_ledgers")
    trust_account = relationship("TrustAccount", back_populates="ledgers")
    client = relationship("Client", back_populates="trust_ledgers")
    case = relationship("Case", back_populates="trust_ledgers")
    transactions = relationship("TrustTransaction", back_populates="ledger", cascade="all, delete-orphan")
