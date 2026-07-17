from datetime import datetime
from pydantic import BaseModel, EmailStr


class InviteCreate(BaseModel):
    email: EmailStr
    role: str


class InviteResponse(BaseModel):
    id: int
    organization_id: int
    email: EmailStr
    role: str
    token: str
    status: str
    expires_at: datetime
    invited_by: int
    created_at: datetime


class AdminUserUpdate(BaseModel):
    role: str | None = None
    status: str | None = None


class AdminUserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str
    status: str = "active"


class AcceptInviteRequest(BaseModel):
    token: str
    name: str
    password: str
