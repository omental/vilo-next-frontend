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
    dedupe_key: str | None = None,
    popup_dismissed_at: datetime | None = None,
    email_status: str | None = None,
) -> Notification:
    notification = Notification(
        organization_id=organization_id,
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        is_read=False,
        dedupe_key=dedupe_key,
        metadata_json=metadata_json,
        popup_dismissed_at=popup_dismissed_at,
        email_status=email_status,
        email_attempts=0,
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
    dedupe_key_prefix: str | None = None,
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
            dedupe_key=f"{dedupe_key_prefix}:user:{user_id}" if dedupe_key_prefix else None,
            metadata_json=metadata_json,
            created_at=now,
        )
        db.add(notification)
        notifications.append(notification)
    await db.flush()
    return notifications
