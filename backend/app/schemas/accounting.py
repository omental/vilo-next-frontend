from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


def _normalize_currency(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {"USD", "JMD"}:
        raise ValueError("Unsupported currency")
    return normalized


class OperatingAccountCreate(BaseModel):
    name: str
    currency: str = "USD"
    is_default: bool = False

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _normalize_currency(value)


class OperatingAccountResponse(BaseModel):
    id: int
    organization_id: int
    name: str
    currency: str
    is_default: bool
    current_balance: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OperatingTransactionResponse(BaseModel):
    id: int
    organization_id: int
    operating_account_id: int
    transaction_type: str
    amount: Decimal
    currency: str
    transaction_date: date
    description: str | None
    linked_invoice_id: int | None
    linked_trust_transaction_id: int | None
    linked_payment_id: int | None
    linked_expense_id: int | None
    reversal_of_id: int | None
    created_by_id: int
    created_at: datetime
    voided_at: datetime | None
    voided_by_id: int | None
    void_reason: str | None


class AccountingCurrencySummary(BaseModel):
    currency: str
    revenue: Decimal = Field(default=Decimal("0.00"))
    expenses: Decimal = Field(default=Decimal("0.00"))
    profit: Decimal = Field(default=Decimal("0.00"))
    operating_balance: Decimal = Field(default=Decimal("0.00"))
    direct_payment_total: Decimal = Field(default=Decimal("0.00"))
    trust_transfer_total: Decimal = Field(default=Decimal("0.00"))
    tax_payable: Decimal = Field(default=Decimal("0.00"))


class AccountingSummaryResponse(BaseModel):
    organization_id: int
    trust_funds_excluded: bool = True
    currencies: list[AccountingCurrencySummary]
