from fastapi import BackgroundTasks

from app.services.email import send_email
from app.services.notifications import create_notification


def enqueue_email(
    background_tasks: BackgroundTasks,
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> None:
    background_tasks.add_task(
        send_email,
        to_email=to_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )


def enqueue_notification(
    background_tasks: BackgroundTasks,
    *,
    db,
    organization_id: int,
    user_id: int,
    type: str,
    title: str,
    body: str | None = None,
    metadata_json: dict | None = None,
    dedupe_key: str | None = None,
) -> None:
    background_tasks.add_task(
        create_notification,
        db=db,
        organization_id=organization_id,
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        metadata_json=metadata_json,
        dedupe_key=dedupe_key,
    )
