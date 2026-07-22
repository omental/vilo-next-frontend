from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.case import Case
from app.models.client import Client, ClientAssignment
from app.models.document import Document
from app.models.invoice import Invoice
from app.models.task import Task
from app.models.user import User
from app.schemas.search import GlobalSearchResponse, SearchResultItem
from app.services.access import accessible_case_condition


router = APIRouter(prefix="/search", tags=["search"])
ALLOWED_STAFF = ["partner", "admin", "lawyer", "paralegal"]


@router.get("", response_model=GlobalSearchResponse)
async def global_search(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    query = q.strip()
    if len(query) < 2:
        return GlobalSearchResponse(query=query, groups={})
    term = f"%{query}%"
    org_id = current_user.organization_id
    case_access = accessible_case_condition(current_user)
    accessible_ids = select(Case.id).where(Case.organization_id == org_id, case_access)

    case_rows = (await db.execute(
        select(Case.id, Case.title, Client.name)
        .join(Client, Client.id == Case.client_id)
        .where(Case.organization_id == org_id, case_access, or_(Case.title.ilike(term), Client.name.ilike(term)))
        .order_by(Case.updated_at.desc()).limit(limit)
    )).all()

    client_access = or_(
        Client.id.in_(select(Case.client_id).where(Case.id.in_(accessible_ids))),
        Client.id.in_(select(ClientAssignment.client_id).where(ClientAssignment.user_id == current_user.id)),
    )
    if current_user.role.value in {"partner", "admin", "lawyer"}:
        client_access = Client.organization_id == org_id
    client_rows = (await db.execute(
        select(Client.id, Client.name, Client.email)
        .where(Client.organization_id == org_id, client_access, or_(Client.name.ilike(term), Client.email.ilike(term)))
        .order_by(Client.updated_at.desc()).limit(limit)
    )).all()

    document_rows = (await db.execute(
        select(Document.id, Document.title, Document.file_name, Case.title)
        .outerjoin(Case, Case.id == Document.case_id)
        .where(
            Document.organization_id == org_id,
            or_(Document.case_id.is_(None), Document.case_id.in_(accessible_ids)),
            or_(Document.title.ilike(term), Document.file_name.ilike(term), Case.title.ilike(term)),
        ).order_by(Document.updated_at.desc()).limit(limit)
    )).all()

    task_access = or_(Task.case_id.is_(None), Task.case_id.in_(accessible_ids))
    if current_user.role.value not in {"partner", "admin", "lawyer"}:
        task_access = or_(Task.assigned_to == current_user.id, Task.created_by == current_user.id, Task.case_id.in_(accessible_ids))
    task_rows = (await db.execute(
        select(Task.id, Task.title, Task.due_date)
        .where(Task.organization_id == org_id, Task.archived_at.is_(None), task_access, Task.title.ilike(term))
        .order_by(Task.updated_at.desc()).limit(limit)
    )).all()

    invoice_rows = (await db.execute(
        select(Invoice.id, Invoice.invoice_number, Client.name)
        .join(Client, Client.id == Invoice.client_id)
        .where(
            Invoice.organization_id == org_id,
            or_(Invoice.case_id.is_(None), Invoice.case_id.in_(accessible_ids)),
            or_(Invoice.invoice_number.ilike(term), Client.name.ilike(term)),
        ).order_by(Invoice.updated_at.desc()).limit(limit)
    )).all()

    user_rows = (await db.execute(
        select(User.id, User.name, User.role)
        .where(User.organization_id == org_id, User.name.ilike(term), User.role != "client")
        .order_by(User.name).limit(limit)
    )).all()

    groups = {
        "Cases": [SearchResultItem(id=row.id, label=row.title, context=f"C-{row.id} · {row.name}", href=f"/dashboard/cases/{row.id}") for row in case_rows],
        "Clients": [SearchResultItem(id=row.id, label=row.name, context=row.email, href=f"/dashboard/clients/{row.id}") for row in client_rows],
        "Documents": [SearchResultItem(id=row.id, label=row.title or row.file_name, context=row[3] or row.file_name, href=f"/dashboard/documents?document_id={row.id}") for row in document_rows],
        "Tasks": [SearchResultItem(id=row.id, label=row.title, context=f"Due {row.due_date.date().isoformat()}" if row.due_date else None, href=f"/dashboard/tasks/{row.id}") for row in task_rows],
        "Invoices": [SearchResultItem(id=row.id, label=row.invoice_number, context=row.name, href=f"/dashboard/invoices/{row.id}") for row in invoice_rows],
        "Staff": [SearchResultItem(id=row.id, label=row.name, context=getattr(row.role, "value", row.role), href="/dashboard/team") for row in user_rows],
    }
    return GlobalSearchResponse(query=query, groups={name: rows for name, rows in groups.items() if rows})
