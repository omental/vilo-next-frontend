from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.calendar_event import CalendarEvent
from app.models.case import Case
from app.models.case_timeline_event import CaseTimelineEvent
from app.models.client import Client
from app.models.expense import Expense
from app.models.invoice import Invoice
from app.models.task import Task
from app.models.time_entry import TimeEntry
from app.models.trust_ledger import TrustLedger
from app.models.trust_transaction import TrustTransaction
from app.services.pdf import generate_report_pdf

router = APIRouter(prefix="/reports", tags=["reports"])
OPER_REPORTS = ["partner", "admin", "lawyer"]
CASE_TASK_REPORTS = ["partner", "admin", "lawyer", "paralegal"]


def d(value):
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@router.get("/dashboard-summary")
async def dashboard_summary(db: AsyncSession = Depends(get_db), current_user=Depends(role_guard(OPER_REPORTS))):
    org_id = current_user.organization_id
    now = datetime.now(timezone.utc)

    total_clients = int((await db.scalar(select(func.count(Client.id)).where(Client.organization_id == org_id))) or 0)
    total_cases = int((await db.scalar(select(func.count(Case.id)).where(Case.organization_id == org_id))) or 0)
    active_cases = int((await db.scalar(select(func.count(Case.id)).where(Case.organization_id == org_id, Case.status == "active"))) or 0)
    closed_cases = int((await db.scalar(select(func.count(Case.id)).where(Case.organization_id == org_id, Case.status == "closed"))) or 0)
    pending_tasks = int((await db.scalar(select(func.count(Task.id)).where(Task.organization_id == org_id, Task.status.in_(["pending", "in_progress"])))) or 0)
    overdue_tasks = int((await db.scalar(select(func.count(Task.id)).where(Task.organization_id == org_id, Task.status.in_(["pending", "in_progress"]), Task.due_date.is_not(None), Task.due_date < now))) or 0)
    upcoming_events = int((await db.scalar(select(func.count(CalendarEvent.id)).where(CalendarEvent.organization_id == org_id, CalendarEvent.start_at >= now))) or 0)
    outstanding_invoices = int((await db.scalar(select(func.count(Invoice.id)).where(Invoice.organization_id == org_id, Invoice.balance_due > 0))) or 0)
    total_invoice_amount = d(await db.scalar(select(func.coalesce(func.sum(Invoice.total), 0)).where(Invoice.organization_id == org_id)))
    total_paid_amount = d(await db.scalar(select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(Invoice.organization_id == org_id)))
    total_balance_due = d(await db.scalar(select(func.coalesce(func.sum(Invoice.balance_due), 0)).where(Invoice.organization_id == org_id)))
    total_trust_balance = d(await db.scalar(select(func.coalesce(func.sum(TrustLedger.current_balance), 0)).where(TrustLedger.organization_id == org_id)))

    recent_activity = (await db.execute(
        select(CaseTimelineEvent.id, CaseTimelineEvent.case_id, CaseTimelineEvent.actor_id, CaseTimelineEvent.event_type, CaseTimelineEvent.title, CaseTimelineEvent.created_at)
        .where(CaseTimelineEvent.organization_id == org_id)
        .order_by(CaseTimelineEvent.created_at.desc()).limit(20)
    )).all()
    upcoming_event_rows = (await db.execute(
        select(CalendarEvent.id, CalendarEvent.title, CalendarEvent.start_at, CalendarEvent.case_id, CalendarEvent.event_type)
        .where(CalendarEvent.organization_id == org_id, CalendarEvent.start_at >= now)
        .order_by(CalendarEvent.start_at.asc()).limit(10)
    )).all()
    overdue_task_rows = (await db.execute(
        select(Task.id, Task.title, Task.due_date, Task.case_id, Task.status)
        .where(Task.organization_id == org_id, Task.status.in_(["pending", "in_progress"]), Task.due_date.is_not(None), Task.due_date < now)
        .order_by(Task.due_date.asc()).limit(10)
    )).all()

    return {
        "total_clients": total_clients,
        "total_cases": total_cases,
        "active_cases": active_cases,
        "closed_cases": closed_cases,
        "pending_tasks": pending_tasks,
        "overdue_tasks": overdue_tasks,
        "upcoming_events": upcoming_events,
        "outstanding_invoices": outstanding_invoices,
        "total_invoice_amount": total_invoice_amount,
        "total_paid_amount": total_paid_amount,
        "total_balance_due": total_balance_due,
        "total_trust_balance": total_trust_balance,
        "recent_activity": [{"id": r.id, "case_id": r.case_id, "actor_id": r.actor_id, "event_type": r.event_type, "title": r.title, "created_at": r.created_at} for r in recent_activity],
        "upcoming_events_items": [{"id": r.id, "title": r.title, "start_at": r.start_at, "case_id": r.case_id, "event_type": r.event_type} for r in upcoming_event_rows],
        "overdue_tasks_items": [{"id": r.id, "title": r.title, "due_date": r.due_date, "case_id": r.case_id, "status": r.status} for r in overdue_task_rows],
        "financial_snapshot": {"invoice_total": total_invoice_amount, "paid_total": total_paid_amount, "balance_due_total": total_balance_due, "trust_balance_total": total_trust_balance},
    }


@router.get("/cases")
async def cases_report(status: str | None = None, priority: str | None = None, client_id: int | None = None, date_from: date | None = None, date_to: date | None = None, db: AsyncSession = Depends(get_db), current_user=Depends(role_guard(CASE_TASK_REPORTS))):
    org_id = current_user.organization_id
    filters = [Case.organization_id == org_id]
    if status: filters.append(Case.status == status)
    if priority: filters.append(Case.priority == priority)
    if client_id: filters.append(Case.client_id == client_id)
    if date_from: filters.append(func.date(Case.created_at) >= date_from)
    if date_to: filters.append(func.date(Case.created_at) <= date_to)

    rows = (await db.execute(select(Case.id, Case.title, Case.status, Case.priority, Case.client_id, Case.created_at).where(and_(*filters)).order_by(Case.created_at.desc()))).all()
    crows = (await db.execute(select(Case.status, func.count(Case.id)).where(and_(*filters)).group_by(Case.status))).all()
    cmap = {k: int(v) for k, v in crows}

    return {
        "cases": [{"id": r.id, "title": r.title, "status": r.status, "priority": r.priority, "client_id": r.client_id, "created_at": r.created_at} for r in rows],
        "total_count": len(rows),
        "status_counts": {"draft": cmap.get("draft", 0), "active": cmap.get("active", 0), "closed": cmap.get("closed", 0), "archived": cmap.get("archived", 0)},
    }


@router.get("/financial")
async def financial_report(date_from: date | None = None, date_to: date | None = None, db: AsyncSession = Depends(get_db), current_user=Depends(role_guard(OPER_REPORTS))):
    org_id = current_user.organization_id
    inv_filters = [Invoice.organization_id == org_id]
    exp_filters = [Expense.organization_id == org_id]
    te_filters = [TimeEntry.organization_id == org_id]
    if date_from:
        inv_filters.append(Invoice.issue_date >= date_from)
        exp_filters.append(Expense.expense_date >= date_from)
        te_filters.append(TimeEntry.entry_date >= date_from)
    if date_to:
        inv_filters.append(Invoice.issue_date <= date_to)
        exp_filters.append(Expense.expense_date <= date_to)
        te_filters.append(TimeEntry.entry_date <= date_to)

    invoice_totals = d(await db.scalar(select(func.coalesce(func.sum(Invoice.total), 0)).where(and_(*inv_filters))))
    paid_totals = d(await db.scalar(select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(and_(*inv_filters))))
    outstanding_totals = d(await db.scalar(select(func.coalesce(func.sum(Invoice.balance_due), 0)).where(and_(*inv_filters))))
    expense_totals = d(await db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(and_(*exp_filters))))
    billable_hours_total = d(await db.scalar(select(func.coalesce(func.sum(TimeEntry.hours), 0)).where(and_(*te_filters), TimeEntry.billable == True)))
    billable_time_total = d(await db.scalar(select(func.coalesce(func.sum(TimeEntry.hours * TimeEntry.rate), 0)).where(and_(*te_filters), TimeEntry.billable == True)))

    month_rows = (await db.execute(
        select(func.date_trunc("month", Invoice.issue_date).label("month"), func.coalesce(func.sum(Invoice.total), 0).label("amount"))
        .where(and_(*inv_filters)).group_by("month").order_by("month")
    )).all()

    return {
        "invoice_totals": invoice_totals,
        "paid_totals": paid_totals,
        "outstanding_totals": outstanding_totals,
        "expense_totals": expense_totals,
        "billable_time_total": billable_time_total,
        "billable_hours_total": billable_hours_total,
        "revenue_by_month": [{"month": r.month, "amount": d(r.amount)} for r in month_rows],
    }


@router.get("/trust")
async def trust_report(db: AsyncSession = Depends(get_db), current_user=Depends(role_guard(OPER_REPORTS))):
    org_id = current_user.organization_id
    total_trust_balance = d(await db.scalar(select(func.coalesce(func.sum(TrustLedger.current_balance), 0)).where(TrustLedger.organization_id == org_id)))
    by_client = (await db.execute(select(TrustLedger.client_id, func.coalesce(func.sum(TrustLedger.current_balance), 0).label("bal")).where(TrustLedger.organization_id == org_id).group_by(TrustLedger.client_id))).all()
    by_case = (await db.execute(select(TrustLedger.case_id, func.coalesce(func.sum(TrustLedger.current_balance), 0).label("bal")).where(TrustLedger.organization_id == org_id).group_by(TrustLedger.case_id))).all()
    recent = (await db.execute(select(TrustTransaction.id, TrustTransaction.transaction_type, TrustTransaction.amount, TrustTransaction.client_id, TrustTransaction.case_id, TrustTransaction.transaction_date).where(TrustTransaction.organization_id == org_id).order_by(TrustTransaction.created_at.desc()).limit(20))).all()

    sum_client = sum((d(r.bal) for r in by_client), Decimal("0"))
    return {
        "total_trust_balance": total_trust_balance,
        "balances_by_client": [{"client_id": r.client_id, "balance": d(r.bal)} for r in by_client],
        "balances_by_case": [{"case_id": r.case_id, "balance": d(r.bal)} for r in by_case],
        "recent_trust_transactions": [{"id": r.id, "transaction_type": r.transaction_type, "amount": d(r.amount), "client_id": r.client_id, "case_id": r.case_id, "transaction_date": r.transaction_date} for r in recent],
        "reconciliation_status": total_trust_balance == sum_client,
    }


@router.get("/tasks")
async def tasks_report(status: str | None = None, assigned_to: int | None = None, case_id: int | None = None, db: AsyncSession = Depends(get_db), current_user=Depends(role_guard(CASE_TASK_REPORTS))):
    org_id = current_user.organization_id
    filters = [Task.organization_id == org_id]
    if status: filters.append(Task.status == status)
    if assigned_to: filters.append(Task.assigned_to == assigned_to)
    if case_id: filters.append(Task.case_id == case_id)

    rows = (await db.execute(select(Task.id, Task.title, Task.status, Task.priority, Task.assigned_to, Task.case_id, Task.due_date).where(and_(*filters)).order_by(Task.created_at.desc()))).all()
    crows = (await db.execute(select(Task.status, func.count(Task.id)).where(and_(*filters)).group_by(Task.status))).all()
    cmap = {k: int(v) for k, v in crows}
    overdue_count = int((await db.scalar(select(func.count(Task.id)).where(and_(*filters), Task.status.in_(["pending", "in_progress"]), Task.due_date.is_not(None), Task.due_date < datetime.now(timezone.utc)))) or 0)

    return {
        "total_tasks": len(rows),
        "pending_count": cmap.get("pending", 0),
        "in_progress_count": cmap.get("in_progress", 0),
        "completed_count": cmap.get("completed", 0),
        "cancelled_count": cmap.get("cancelled", 0),
        "overdue_count": overdue_count,
        "tasks": [{"id": r.id, "title": r.title, "status": r.status, "priority": r.priority, "assigned_to": r.assigned_to, "case_id": r.case_id, "due_date": r.due_date} for r in rows],
    }


@router.get("/activity")
async def activity_report(db: AsyncSession = Depends(get_db), current_user=Depends(role_guard(OPER_REPORTS))):
    org_id = current_user.organization_id
    rows = (await db.execute(
        select(CaseTimelineEvent.id, CaseTimelineEvent.case_id, CaseTimelineEvent.actor_id, CaseTimelineEvent.event_type, CaseTimelineEvent.title, CaseTimelineEvent.created_at)
        .where(CaseTimelineEvent.organization_id == org_id)
        .order_by(CaseTimelineEvent.created_at.desc()).limit(100)
    )).all()
    return {"activity": [{"id": r.id, "case_id": r.case_id, "actor_id": r.actor_id, "event_type": r.event_type, "title": r.title, "created_at": r.created_at} for r in rows]}


@router.get("/financial/pdf")
async def financial_report_pdf(
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(role_guard(OPER_REPORTS)),
):
    generated = await generate_report_pdf(
        "financial",
        {"date_from": date_from, "date_to": date_to},
        db=db,
        organization_id=current_user.organization_id,
    )
    return FileResponse(path=str(generated.file_path), filename=generated.filename, media_type="application/pdf")


@router.get("/trust/pdf")
async def trust_report_pdf(db: AsyncSession = Depends(get_db), current_user=Depends(role_guard(OPER_REPORTS))):
    generated = await generate_report_pdf("trust", {}, db=db, organization_id=current_user.organization_id)
    return FileResponse(path=str(generated.file_path), filename=generated.filename, media_type="application/pdf")


@router.get("/cases/pdf")
async def cases_report_pdf(
    status: str | None = None,
    priority: str | None = None,
    client_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(role_guard(CASE_TASK_REPORTS)),
):
    generated = await generate_report_pdf(
        "cases",
        {"status": status, "priority": priority, "client_id": client_id, "date_from": date_from, "date_to": date_to},
        db=db,
        organization_id=current_user.organization_id,
    )
    return FileResponse(path=str(generated.file_path), filename=generated.filename, media_type="application/pdf")
