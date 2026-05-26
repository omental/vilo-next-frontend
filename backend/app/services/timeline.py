from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case_timeline_event import CaseTimelineEvent


async def create_case_timeline_event(
    db: AsyncSession,
    *,
    organization_id: int,
    case_id: int,
    event_type: str,
    title: str,
    description: str | None = None,
    actor_id: int | None = None,
    metadata_json: dict | None = None,
) -> CaseTimelineEvent:
    event = CaseTimelineEvent(
        organization_id=organization_id,
        case_id=case_id,
        actor_id=actor_id,
        event_type=event_type,
        title=title,
        description=description,
        metadata_json=metadata_json,
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()
    return event
