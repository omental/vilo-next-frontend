from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


VALID_BILLING_TYPES = {"professional_fee", "disbursement", "non_billable", "invoiced", "no_charge"}
VALID_STATUSES = {"draft", "billable", "non_billable", "invoiced"}


class TimeEntryBase(BaseModel):
    case_id: int | None = None
    client_id: int | None = None
    user_id: int | None = None
    invoice_id: int | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_minutes: int | None = None
    billing_type: str = "professional_fee"
    currency: str = "USD"
    hourly_rate: Decimal | None = None
    rate_is_manual: bool | None = None
    status: str | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        normalized = (value or "USD").strip().upper()
        if normalized not in {"USD", "JMD"}:
            raise ValueError("Unsupported currency")
        return normalized

    @field_validator("billing_type")
    @classmethod
    def validate_billing_type(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in VALID_BILLING_TYPES:
            raise ValueError("Invalid billing type")
        return normalized

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in VALID_STATUSES:
            raise ValueError("Invalid time entry status")
        return normalized

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("Duration must be positive")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class TimeEntryCreate(TimeEntryBase):
    billing_type: str = "professional_fee"


class TimeEntryUpdate(TimeEntryBase):
    billing_type: str | None = None

    @field_validator("billing_type")
    @classmethod
    def validate_optional_billing_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in VALID_BILLING_TYPES:
            raise ValueError("Invalid billing type")
        return normalized


class TimeEntryResponse(BaseModel):
    id: int
    organization_id: int
    case_id: int | None
    client_id: int | None
    user_id: int
    invoice_id: int | None
    description: str | None
    start_time: datetime | None
    end_time: datetime | None
    duration_minutes: int | None
    billing_type: str
    currency: str
    hourly_rate: Decimal | None
    rate_is_manual: bool
    amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
    case_title: str | None = None
    case_display_number: str | None = None
    client_name: str | None = None
    staff_name: str | None = None
    invoice_number: str | None = None


class TimeEntryListResponse(BaseModel):
    items: list[TimeEntryResponse] = Field(default_factory=list)
    total: int
    page: int
    per_page: int
    total_pages: int
