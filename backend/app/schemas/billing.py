from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


def _normalize_currency(value: str) -> str:
    normalized = (value or "USD").strip().upper()
    if normalized not in {"USD", "JMD"}:
        raise ValueError("Unsupported currency")
    return normalized


class FirmPaymentAccountCreate(BaseModel):
    account_name: str
    bank_name: str
    account_number: str
    currency: str = "USD"
    swift_routing: str | None = None
    notes: str | None = None
    payment_instructions: str | None = None
    is_default: bool = False

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _normalize_currency(value)


class FirmPaymentAccountUpdate(BaseModel):
    account_name: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    currency: str | None = None
    swift_routing: str | None = None
    notes: str | None = None
    payment_instructions: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_currency(value)


class FirmPaymentAccountResponse(BaseModel):
    id: int
    organization_id: int
    account_name: str
    bank_name: str
    account_number: str
    currency: str
    swift_routing: str | None
    notes: str | None
    payment_instructions: str | None
    is_default: bool
    is_active: bool
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class BillingRateCreate(BaseModel):
    rate_type: str
    role_name: str | None = None
    user_id: int | None = None
    currency: str = "USD"
    hourly_rate: Decimal = Field(ge=Decimal("0"))
    is_active: bool = True

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _normalize_currency(value)


class BillingRateUpdate(BaseModel):
    role_name: str | None = None
    user_id: int | None = None
    currency: str | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=Decimal("0"))
    is_active: bool | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_currency(value)


class BillingRateResponse(BaseModel):
    id: int
    organization_id: int
    rate_type: str
    role_name: str | None
    user_id: int | None
    currency: str
    hourly_rate: Decimal
    is_active: bool
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class EffectiveBillingRateResponse(BaseModel):
    user_id: int
    currency: str
    hourly_rate: Decimal
    source: str
    rate_id: int | None = None


class BillingTaxSettingsResponse(BaseModel):
    invoice_tax_label: str
    invoice_tax_rate: Decimal


class BillingTaxSettingsUpdate(BaseModel):
    invoice_tax_label: str = Field(min_length=1, max_length=50)
    invoice_tax_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))


class RevenueByStaffRow(BaseModel):
    staff_user_id: int
    staff_name: str
    currency: str
    total_billed: Decimal
    total_collected: Decimal
    invoice_count: int
    direct_collected: Decimal
    trust_collected: Decimal


class TimeByStaffRow(BaseModel):
    staff_user_id: int
    staff_name: str
    currency: str
    total_hours: Decimal
    billable_hours: Decimal
    estimated_value: Decimal
