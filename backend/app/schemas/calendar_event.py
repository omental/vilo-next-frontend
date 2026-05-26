from datetime import datetime
from pydantic import BaseModel


class CalendarEventCreate(BaseModel):
    case_id: int | None = None
    title: str
    description: str | None = None
    event_type: str
    start_at: datetime
    end_at: datetime | None = None
    location: str | None = None


class CalendarEventUpdate(BaseModel):
    case_id: int | None = None
    title: str | None = None
    description: str | None = None
    event_type: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    location: str | None = None


class CalendarEventResponse(BaseModel):
    id: int
    organization_id: int
    case_id: int | None
    created_by: int
    title: str
    description: str | None
    event_type: str
    start_at: datetime
    end_at: datetime | None
    location: str | None
    created_at: datetime
    updated_at: datetime
