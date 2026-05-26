from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


class TrustAccountCreate(BaseModel):
    name: str
    bank_name: str | None = None
    account_number_last4: str | None = None
    status: str = "active"


class TrustAccountResponse(BaseModel):
    id: int
    organization_id: int
    name: str
    bank_name: str | None
    account_number_last4: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class TrustLedgerResponse(BaseModel):
    id: int
    organization_id: int
    trust_account_id: int
    client_id: int
    case_id: int | None
    current_balance: Decimal
    created_at: datetime
    updated_at: datetime


class TrustTxnCreate(BaseModel):
    trust_account_id: int
    client_id: int
    case_id: int | None = None
    amount: Decimal
    description: str | None = None
    transaction_date: date


class TrustAdjustmentCreate(TrustTxnCreate):
    direction: str


class TrustApplyToInvoiceCreate(BaseModel):
    trust_account_id: int
    client_id: int
    case_id: int | None = None
    invoice_id: int
    amount: Decimal
    description: str | None = None


class TrustTransactionResponse(BaseModel):
    id: int
    organization_id: int
    trust_account_id: int
    ledger_id: int
    client_id: int
    case_id: int | None
    invoice_id: int | None
    transaction_type: str
    amount: Decimal
    description: str | None
    transaction_date: date
    created_by: int
    created_at: datetime


class TrustReceiptResponse(BaseModel):
    receipt_number: str
    client: int
    case: int | None
    amount: Decimal
    date: date
    payment_method: str | None = None
    description: str | None
    trust_account: int


class TrustReconciliationSummary(BaseModel):
    total_trust_account_balance: Decimal
    total_client_ledger_balances: Decimal
    total_matter_case_balances: Decimal
    matches: bool
