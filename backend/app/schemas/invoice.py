from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class InvoiceOrganizationSummary(BaseModel):
    id: int
    name: str
    address: str | None = None
    email: str | None = None
    phone: str | None = None
    tax_number: str | None = None


class InvoiceClientSummary(BaseModel):
    id: int
    name: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    occupation: str | None = None
    tax_number: str | None = None


class InvoiceCreate(BaseModel):
    client_id: int
    case_id: int | None = None
    issue_date: date
    due_date: date | None = None
    notes: str | None = None


class InvoiceUpdate(BaseModel):
    status: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    tax_amount: Decimal | None = None
    notes: str | None = None


class InvoiceApplyTrustRequest(BaseModel):
    amount: Decimal = Field(gt=Decimal("0"))
    trust_account_id: int | None = None
    currency: str | None = None
    description: str | None = None
    reference_number: str | None = None
    payment_date: date | None = None


class InvoicePaymentVoidRequest(BaseModel):
    void_reason: str = Field(min_length=1)
    void_date: date | None = None
    description: str | None = None


class InvoiceLineItemResponse(BaseModel):
    id: int
    organization_id: int
    invoice_id: int
    line_type: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    time_entry_id: int | None
    expense_id: int | None
    created_at: datetime


class InvoicePaymentResponse(BaseModel):
    id: int
    amount: Decimal
    currency: str
    payment_method: str | None
    payment_source: str
    paid_at: date
    reference_number: str | None
    description: str | None
    linked_trust_transaction_id: int | None
    linked_operating_transaction_id: int | None
    created_by_id: int
    created_at: datetime
    voided_at: datetime | None
    voided_by_id: int | None
    void_reason: str | None


class InvoiceResponse(BaseModel):
    id: int
    organization_id: int
    client_id: int
    case_id: int | None
    invoice_number: str
    status: str
    issue_date: date
    due_date: date | None
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    paid_amount: Decimal
    balance_due: Decimal
    notes: str | None
    created_by: int
    created_at: datetime
    updated_at: datetime
    organization: InvoiceOrganizationSummary
    client: InvoiceClientSummary
    line_items: list[InvoiceLineItemResponse] = []
    payments: list[InvoicePaymentResponse] = []
    trust_balance_available: Decimal | None = None
    can_apply_trust: bool = False


class InvoicePaymentSummaryResponse(BaseModel):
    invoice_id: int
    invoice_number: str
    total: Decimal
    paid_amount: Decimal
    balance_due: Decimal
    trust_balance_available: Decimal
    can_apply_trust: bool
    payments: list[InvoicePaymentResponse] = []


class InvoiceTrustApplyResponse(BaseModel):
    invoice: InvoiceResponse
    payment: InvoicePaymentResponse
    trust_transaction_id: int
    operating_transaction_id: int


class InvoicePaymentVoidResponse(BaseModel):
    invoice: InvoiceResponse
    payment: InvoicePaymentResponse
    reversal_operating_transaction_id: int
    reversal_trust_transaction_id: int | None = None


class InvoiceSummaryResponse(BaseModel):
    invoice_id: int
    invoice_number: str
    status: str
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    paid_amount: Decimal
    balance_due: Decimal
    line_items_count: int
