from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field


class AssignedUser(BaseModel):
    id: int
    name: str
    email: str
    role: str
    status: str


class ClientCreate(BaseModel):
    name: str
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    user_id: int | None = None
    client_type: str = "individual"
    trn_no: str | None = None
    occupation: str | None = None
    preferred_contact_method: str | None = None
    date_of_birth: date | None = None
    billing_currency: str | None = "USD"
    archived_at: datetime | None = None
    assigned_user_ids: list[int] = Field(default_factory=list)


class ClientUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    user_id: int | None = None
    client_type: str | None = None
    trn_no: str | None = None
    occupation: str | None = None
    preferred_contact_method: str | None = None
    date_of_birth: date | None = None
    billing_currency: str | None = None
    archived_at: datetime | None = None
    assigned_user_ids: list[int] | None = None


class ClientResponse(BaseModel):
    id: int
    organization_id: int
    name: str
    email: EmailStr | None
    phone: str | None
    user_id: int | None
    address: str | None
    notes: str | None
    client_type: str
    trn_no: str | None
    occupation: str | None
    preferred_contact_method: str | None
    date_of_birth: date | None
    billing_currency: str | None
    archived_at: datetime | None
    assigned_users: list[AssignedUser]
    assigned_user_ids: list[int]
    created_at: datetime
    updated_at: datetime
