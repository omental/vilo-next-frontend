from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.case import Case
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.email import build_task_assignment_email
from app.services.jobs import enqueue_email
from app.services.notifications import create_notification
from app.services.timeline import create_case_timeline_event

router = APIRouter(prefix="/tasks", tags=["tasks"])
ALLOWED_STAFF = ["partner", "admin", "lawyer", "paralegal"]
VALID_STATUS = {"pending", "in_progress", "completed", "cancelled"}
VALID_PRIORITY = {"low", "medium", "high", "urgent"}


def serialize(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        organization_id=task.organization_id,
        case_id=task.case_id,
        assigned_to=task.assigned_to,
        created_by=task.created_by,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        due_date=task.due_date,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


async def validate_case(db: AsyncSession, organization_id: int, case_id: int | None) -> None:
    if case_id is None:
        return
    case = await db.scalar(select(Case).where(Case.id == case_id, Case.organization_id == organization_id))
    if not case:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case must belong to your organization")


async def validate_user(db: AsyncSession, organization_id: int, user_id: int | None) -> None:
    if user_id is None:
        return
    user = await db.scalar(select(User).where(User.id == user_id, User.organization_id == organization_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignee must belong to your organization")


def validate_values(status_value: str | None, priority_value: str | None) -> None:
    if status_value is not None and status_value not in VALID_STATUS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task status")
    if priority_value is not None and priority_value not in VALID_PRIORITY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task priority")


@router.post("", response_model=TaskResponse)
async def create_task(
    payload: TaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    validate_values(payload.status, payload.priority)
    await validate_case(db, current_user.organization_id, payload.case_id)
    await validate_user(db, current_user.organization_id, payload.assigned_to)

    now = datetime.now(timezone.utc)
    task = Task(
        organization_id=current_user.organization_id,
        case_id=payload.case_id,
        assigned_to=payload.assigned_to,
        created_by=current_user.id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        due_date=payload.due_date,
        completed_at=now if payload.status == "completed" else None,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    await db.flush()

    if task.case_id:
        await create_case_timeline_event(
            db,
            organization_id=current_user.organization_id,
            case_id=task.case_id,
            actor_id=current_user.id,
            event_type="task_created",
            title=f"Task created: {task.title}",
            metadata_json={"task_id": task.id, "status": task.status, "priority": task.priority},
        )
    if task.assigned_to and task.assigned_to != current_user.id:
        assignee = await db.scalar(select(User).where(User.id == task.assigned_to, User.organization_id == current_user.organization_id))
        await create_notification(
            db,
            organization_id=current_user.organization_id,
            user_id=task.assigned_to,
            type="task_assigned",
            title=f"Task assigned: {task.title}",
            body=f"You were assigned a task by {current_user.name}.",
            metadata_json={"task_id": task.id, "case_id": task.case_id},
        )
        if assignee and assignee.email:
            subject, html_body, text_body = build_task_assignment_email(assignee_name=assignee.name, task_title=task.title, task_id=task.id)
            enqueue_email(background_tasks, to_email=assignee.email, subject=subject, html_body=html_body, text_body=text_body)

    await db.commit()
    await db.refresh(task)
    return serialize(task)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    case_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    query = select(Task).where(Task.organization_id == current_user.organization_id)
    if case_id is not None:
        query = query.where(Task.case_id == case_id)
    rows = await db.scalars(query.order_by(Task.created_at.desc()))
    return [serialize(t) for t in rows.all()]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    task = await db.scalar(select(Task).where(Task.id == task_id, Task.organization_id == current_user.organization_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return serialize(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    task = await db.scalar(select(Task).where(Task.id == task_id, Task.organization_id == current_user.organization_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    updates = payload.model_dump(exclude_unset=True)
    validate_values(updates.get("status"), updates.get("priority"))

    if "case_id" in updates:
        await validate_case(db, current_user.organization_id, updates["case_id"])
    if "assigned_to" in updates:
        await validate_user(db, current_user.organization_id, updates["assigned_to"])
    previous_assigned_to = task.assigned_to

    for key, value in updates.items():
        setattr(task, key, value)

    if task.status == "completed" and task.completed_at is None:
        task.completed_at = datetime.now(timezone.utc)
    if task.status != "completed":
        task.completed_at = None

    task.updated_at = datetime.now(timezone.utc)
    if task.assigned_to and task.assigned_to != current_user.id and task.assigned_to != previous_assigned_to:
        assignee = await db.scalar(select(User).where(User.id == task.assigned_to, User.organization_id == current_user.organization_id))
        await create_notification(
            db,
            organization_id=current_user.organization_id,
            user_id=task.assigned_to,
            type="task_assigned",
            title=f"Task assigned: {task.title}",
            body=f"You were assigned a task by {current_user.name}.",
            metadata_json={"task_id": task.id, "case_id": task.case_id},
        )
        if assignee and assignee.email:
            subject, html_body, text_body = build_task_assignment_email(assignee_name=assignee.name, task_title=task.title, task_id=task.id)
            enqueue_email(background_tasks, to_email=assignee.email, subject=subject, html_body=html_body, text_body=text_body)
    await db.commit()
    await db.refresh(task)
    return serialize(task)


@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    task = await db.scalar(select(Task).where(Task.id == task_id, Task.organization_id == current_user.organization_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    now = datetime.now(timezone.utc)
    task.status = "completed"
    task.completed_at = now
    task.updated_at = now

    if task.case_id:
        await create_case_timeline_event(
            db,
            organization_id=current_user.organization_id,
            case_id=task.case_id,
            actor_id=current_user.id,
            event_type="task_completed",
            title=f"Task completed: {task.title}",
            metadata_json={"task_id": task.id},
        )

    await db.commit()
    await db.refresh(task)
    return serialize(task)


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    task = await db.scalar(select(Task).where(Task.id == task_id, Task.organization_id == current_user.organization_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    await db.delete(task)
    await db.commit()
    return {"ok": True}
