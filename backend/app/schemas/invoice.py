from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


def _normalize_currency(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {"USD", "JMD"}:
        raise ValueError("Unsupported currency")
    return normalized


class InvoiceLineItemCreate(BaseModel):
    line_type: str
    description: str = Field(min_length=1)
    quantity: Decimal | None = Field(default=None, gt=Decimal("0"))
    unit_price: Decimal | None = Field(default=None, ge=Decimal("0"))
    amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    time_entry_id: int | None = None
    staff_user_id: int | None = None
    hours: Decimal | None = Field(default=None, ge=Decimal("0"))
    rate: Decimal | None = Field(default=None, ge=Decimal("0"))

    @model_validator(mode="after")
    def validate_pricing_fields(self):
        if self.time_entry_id is None and (self.quantity is None or self.unit_price is None):
            raise ValueError("quantity and unit_price are required when time_entry_id is not supplied")
        return self


class InvoicePaymentAccountSummary(BaseModel):
    id: int
    account_name: str
    bank_name: str
    account_number: str
    currency: str
    swift_routing: str | None = None
    notes: str | None = None
    payment_instructions: str | None = None


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
    case_id: int
    invoice_number: str | None = None
    currency: str = "USD"
    issue_date: date
    due_date: date | None = None
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    notes: str | None = None
    payment_instructions: str | None = None
    payment_account_id: int | None = None
    line_items: list[InvoiceLineItemCreate] = []

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _normalize_currency(value)


class InvoiceUpdate(BaseModel):
    client_id: int | None = None
    case_id: int | None = None
    invoice_number: str | None = None
    status: str | None = None
    currency: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    tax_amount: Decimal | None = None
    notes: str | None = None
    payment_instructions: str | None = None
    payment_account_id: int | None = None
    line_items: list[InvoiceLineItemCreate] | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _normalize_currency(value)


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
    hours: Decimal | None
    rate: Decimal | None
    time_entry_id: int | None
    expense_id: int | None
    staff_user_id: int | None
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
    currency: str
    status: str
    display_status: str
    payment_method_summary: str
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
    payment_instructions: str | None
    payment_account_id: int | None
    payment_account: InvoicePaymentAccountSummary | None = None
    organization: InvoiceOrganizationSummary
    client: InvoiceClientSummary
    matter_title: str | None = None
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
