from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_currency(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {"USD", "JMD"}:
        raise ValueError("Unsupported currency")
    return normalized


class InvoiceLineItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    quantity: Decimal | None = Field(default=None, gt=Decimal("0"))
    unit_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    time_entry_id: int | None = None
    staff_user_id: int | None = None
    hours: Decimal | None = Field(default=None, ge=Decimal("0"))
    rate: Decimal | None = Field(default=None, ge=Decimal("0"))

    @model_validator(mode="after")
    def validate_pricing_fields(self):
        if self.time_entry_id is None and (self.quantity is None or self.unit_price is None):
            raise ValueError("quantity and unit_price are required when time_entry_id is not supplied")
        if self.time_entry_id is None and self.amount is not None:
            calculated = (self.quantity * self.unit_price).quantize(Decimal("0.01"))
            if self.amount.quantize(Decimal("0.01")) != calculated:
                raise ValueError("amount must equal quantity multiplied by unit_price")
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
    model_config = ConfigDict(extra="forbid")

    client_id: int | None = None
    manual_client_name: str | None = Field(default=None, max_length=255)
    case_id: int | None = None
    invoice_number: str | None = None
    currency: str = "JMD"
    issue_date: date
    due_date: date | None = None
    notes: str | None = None
    payment_instructions: str | None = None
    payment_account_id: int | None = None
    line_items: list[InvoiceLineItemCreate] = Field(min_length=1)
    subtotal: Decimal | None = Field(default=None, ge=Decimal("0"))
    tax_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    total: Decimal | None = Field(default=None, ge=Decimal("0"))

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _normalize_currency(value)

    @model_validator(mode="after")
    def validate_invoice(self):
        manual_name = (self.manual_client_name or "").strip()
        self.manual_client_name = manual_name or None
        if (self.client_id is None) == (self.manual_client_name is None):
            raise ValueError("Provide exactly one of client_id or manual_client_name")
        if self.manual_client_name and self.case_id is not None:
            raise ValueError("Manual invoice recipients cannot be linked to a case")
        if self.due_date is not None and self.due_date < self.issue_date:
            raise ValueError("due_date cannot be before issue_date")
        return self


class InvoiceUpdate(BaseModel):
    client_id: int | None = None
    manual_client_name: str | None = Field(default=None, max_length=255)
    case_id: int | None = None
    invoice_number: str | None = None
    status: str | None = None
    currency: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
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
    external_reference_number: str | None = None
    payment_date: date | None = None


class InvoicePaymentVoidRequest(BaseModel):
    void_reason: str = Field(min_length=1)
    void_date: date | None = None
    description: str | None = None


class InvoiceVoidRequest(BaseModel):
    void_reason: str = Field(min_length=1)


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
    client_id: int | None
    manual_client_name: str | None = None
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
    voided_at: datetime | None = None
    voided_by_id: int | None = None
    void_reason: str | None = None
    payment_account: InvoicePaymentAccountSummary | None = None
    organization: InvoiceOrganizationSummary
    client: InvoiceClientSummary | None
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
