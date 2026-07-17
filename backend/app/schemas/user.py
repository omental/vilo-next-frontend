from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: int
    organization_id: int
    name: str
    email: EmailStr
    role: str
    status: str
    organization_name: str | None = None
    profile_image_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserProfileUpdate(BaseModel):
    name: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str
