from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


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
    line_items: list[InvoiceLineItemResponse] = []


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
