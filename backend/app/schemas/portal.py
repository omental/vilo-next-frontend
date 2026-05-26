from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, EmailStr

from app.schemas.invoice import InvoiceLineItemResponse


class PortalProfileResponse(BaseModel):
    client_id: int
    organization_id: int
    organization_name: str
    name: str
    email: EmailStr | None
    phone: str | None
    address: str | None
    notes: str | None
    linked_user: dict


class PortalCaseResponse(BaseModel):
    id: int
    title: str
    description: str | None
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime


class PortalTimelineResponse(BaseModel):
    id: int
    event_type: str
    title: str
    description: str | None
    created_at: datetime


class PortalDocumentResponse(BaseModel):
    id: int
    case_id: int | None
    title: str
    description: str | None
    file_name: str
    file_type: str | None
    category: str | None
    created_at: datetime


class PortalCaseNoteResponse(BaseModel):
    id: int
    case_id: int
    note: str
    visibility: str
    created_at: datetime
    updated_at: datetime


class PortalInvoiceResponse(BaseModel):
    id: int
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
    created_at: datetime


class PortalInvoiceDetailResponse(PortalInvoiceResponse):
    line_items: list[InvoiceLineItemResponse] = []


class ClientIntakeCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    address: str | None = None
    matter_type: str | None = None
    description: str | None = None


class ClientIntakeUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    matter_type: str | None = None
    description: str | None = None


class ClientIntakeResponse(BaseModel):
    id: int
    organization_id: int
    client_id: int
    submitted_by: int
    status: str
    full_name: str
    email: EmailStr
    phone: str
    address: str | None
    matter_type: str | None
    description: str | None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
