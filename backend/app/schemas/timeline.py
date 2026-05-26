from datetime import datetime
from pydantic import BaseModel


class CaseTimelineResponse(BaseModel):
    id: int
    organization_id: int
    case_id: int
    actor_id: int | None
    event_type: str
    title: str
    description: str | None
    metadata: dict | None = None
    created_at: datetime
