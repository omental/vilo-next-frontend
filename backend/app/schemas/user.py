from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: int
    organization_id: int
    name: str
    email: EmailStr
    role: str
    status: str
    created_at: datetime
    updated_at: datetime
