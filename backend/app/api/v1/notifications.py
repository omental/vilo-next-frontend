from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import MarkNotificationsReadRequest, NotificationListResponse, NotificationResponse
from app.services.reminders import process_due_reminders

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await process_due_reminders(db)
    base_filters = [
        Notification.organization_id == current_user.organization_id,
        Notification.user_id == current_user.id,
    ]
    offset = (page - 1) * page_size
    rows = (
        await db.scalars(
            select(Notification)
            .where(*base_filters)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
    ).all()
    total = int((await db.scalar(select(func.count(Notification.id)).where(*base_filters))) or 0)
    unread_count = int(
        (
            await db.scalar(
                select(func.count(Notification.id)).where(
                    *base_filters,
                    Notification.is_read.is_(False),
                )
            )
        )
        or 0
    )
    return NotificationListResponse(
        items=[
            NotificationResponse(
                id=n.id,
                type=n.type,
                title=n.title,
                body=n.body,
                is_read=n.is_read,
                metadata=n.metadata_json,
                created_at=n.created_at,
            )
            for n in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread_count,
    )


@router.post("/mark-read")
async def mark_notifications_read(
    payload: MarkNotificationsReadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not payload.notification_ids:
        return {"ok": True}
    await db.execute(
        update(Notification)
        .where(
            Notification.organization_id == current_user.organization_id,
            Notification.user_id == current_user.id,
            Notification.id.in_(payload.notification_ids),
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}


@router.post("/mark-all-read")
async def mark_all_notifications_read(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await db.execute(
        update(Notification)
        .where(
            Notification.organization_id == current_user.organization_id,
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}
