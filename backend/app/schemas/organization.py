from datetime import datetime
from pydantic import BaseModel


class OrganizationOut(BaseModel):
    id: int
    name: str
    slug: str
    status: str
    created_at: datetime
    updated_at: datetime
