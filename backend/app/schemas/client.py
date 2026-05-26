from datetime import datetime
from pydantic import BaseModel, EmailStr


class ClientCreate(BaseModel):
    name: str
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    user_id: int | None = None


class ClientUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    user_id: int | None = None


class ClientResponse(BaseModel):
    id: int
    organization_id: int
    name: str
    email: EmailStr | None
    phone: str | None
    user_id: int | None
    address: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
