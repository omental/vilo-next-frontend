from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


async def create_notification(
    db: AsyncSession,
    *,
    organization_id: int,
    user_id: int,
    type: str,
    title: str,
    body: str | None = None,
    metadata_json: dict | None = None,
) -> Notification:
    notification = Notification(
        organization_id=organization_id,
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        is_read=False,
        metadata_json=metadata_json,
        created_at=datetime.now(timezone.utc),
    )
    db.add(notification)
    await db.flush()
    return notification


async def bulk_create_notifications(
    db: AsyncSession,
    *,
    organization_id: int,
    user_ids: list[int],
    type: str,
    title: str,
    body: str | None = None,
    metadata_json: dict | None = None,
) -> list[Notification]:
    now = datetime.now(timezone.utc)
    notifications: list[Notification] = []
    for user_id in sorted(set(user_ids)):
        notification = Notification(
            organization_id=organization_id,
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            is_read=False,
            metadata_json=metadata_json,
            created_at=now,
        )
        db.add(notification)
        notifications.append(notification)
    await db.flush()
    return notifications
