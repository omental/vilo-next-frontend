from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


VALID_TRUST_TRANSACTION_TYPES = {
    "deposit",
    "disbursement",
    "refund",
    "transfer_to_operating",
    "adjustment",
}
VALID_TRUST_ACCOUNT_TYPES = {"pooled", "separate"}
VALID_ADJUSTMENT_DIRECTIONS = {"increase", "decrease"}


def _normalize_currency(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {"USD", "JMD"}:
        raise ValueError("Unsupported currency")
    return normalized


class TrustAccountCreate(BaseModel):
    name: str
    currency: str = "USD"
    account_type: str = "pooled"
    is_default: bool = False
    opening_balance: Decimal = Decimal("0.00")
    bank_name: str | None = None
    account_number_last4: str | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _normalize_currency(value)

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_TRUST_ACCOUNT_TYPES:
            raise ValueError("Unsupported trust account type")
        return normalized


class TrustAccountResponse(BaseModel):
    id: int
    organization_id: int
    name: str
    currency: str
    account_type: str
    is_default: bool
    opening_balance: Decimal
    current_balance: Decimal
    is_active: bool
    bank_name: str | None
    account_number_last4: str | None
    created_at: datetime
    updated_at: datetime


class TrustTransactionCreate(BaseModel):
    trust_account_id: int
    client_id: int
    case_id: int
    transaction_type: str = "deposit"
    amount: Decimal = Field(gt=Decimal("0"))
    currency: str = "USD"
    transaction_date: date
    description: str
    payee_name: str | None = None
    payee_type: str | None = None
    payment_method: str | None = None
    reference_number: str | None = None
    adjustment_direction: str | None = None
    adjustment_reason: str | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _normalize_currency(value)

    @field_validator("transaction_type")
    @classmethod
    def validate_transaction_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_TRUST_TRANSACTION_TYPES:
            raise ValueError("Unsupported trust transaction type")
        return normalized

    @field_validator("adjustment_direction")
    @classmethod
    def validate_adjustment_direction(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in VALID_ADJUSTMENT_DIRECTIONS:
            raise ValueError("Unsupported adjustment direction")
        return normalized

    @model_validator(mode="after")
    def validate_phase_b_fields(self) -> "TrustTransactionCreate":
        if not self.description or not self.description.strip():
            raise ValueError("Description is required")
        if self.transaction_type == "disbursement" and not self.payee_name:
            raise ValueError("payee_name is required for disbursements")
        if self.transaction_type == "adjustment":
            if not self.adjustment_direction:
                raise ValueError("adjustment_direction is required for adjustments")
            if not self.adjustment_reason or not self.adjustment_reason.strip():
                raise ValueError("adjustment_reason is required for adjustments")
        return self


class TrustTransactionVoidRequest(BaseModel):
    void_reason: str

    @field_validator("void_reason")
    @classmethod
    def validate_void_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("void_reason is required")
        return normalized


class TrustTransactionResponse(BaseModel):
    id: int
    organization_id: int
    trust_account_id: int
    ledger_id: int
    client_id: int
    case_id: int | None
    linked_invoice_id: int | None
    transaction_type: str
    amount: Decimal
    currency: str
    transaction_date: date
    description: str | None
    payee_name: str | None
    payee_type: str | None
    payment_method: str | None
    reference_number: str | None
    adjustment_reason: str | None
    adjustment_direction: str | None
    reversal_of_id: int | None
    created_by_id: int
    created_at: datetime
    voided_at: datetime | None
    voided_by_id: int | None
    void_reason: str | None
    receipt_id: int | None = None


class TrustReceiptResponse(BaseModel):
    id: int
    receipt_number: str
    trust_transaction_id: int
    client_id: int
    case_id: int
    amount: Decimal
    currency: str
    payment_method: str | None = None
    description: str | None = None
    issued_at: datetime
    issued_by_id: int
    pdf_available: bool = False
    voided_at: datetime | None = None
    voided_by_id: int | None = None
    void_reason: str | None = None


class TrustBalanceResponse(BaseModel):
    trust_account_id: int | None = None
    client_id: int | None = None
    case_id: int | None = None
    trust_account_balance: Decimal | None = None
    client_balance: Decimal | None = None
    matter_balance: Decimal | None = None
    currency: str
    as_of: datetime


class TrustClientLedgerRow(BaseModel):
    client_id: int
    client_name: str
    currency: str
    balance: Decimal


class TrustMatterLedgerRow(BaseModel):
    case_id: int
    case_title: str
    client_id: int
    client_name: str
    currency: str
    balance: Decimal


class TrustVoidResponse(BaseModel):
    original_transaction: TrustTransactionResponse
    reversal_transaction: TrustTransactionResponse


class TrustReconciliationResponse(BaseModel):
    id: int
    organization_id: int
    trust_account_id: int
    period_start: date
    period_end: date
    bank_statement_balance: Decimal
    ledger_balance: Decimal
    client_ledger_total: Decimal
    matter_ledger_total: Decimal
    difference: Decimal
    status: str
    prepared_by_id: int | None
    prepared_at: datetime | None
    notes: str | None
