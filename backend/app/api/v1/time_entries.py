from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.case import Case
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.schemas.time_entry import TimeEntryCreate, TimeEntryListResponse, TimeEntryResponse, TimeEntryUpdate
from app.services.timeline import create_case_timeline_event

router = APIRouter(prefix="/time-entries", tags=["time-entries"])
ALLOWED = ["partner", "admin", "lawyer", "paralegal"]
ZERO = Decimal("0.00")


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _entry_hours(duration_minutes: int | None) -> Decimal:
    if not duration_minutes:
        return Decimal("0.00")
    return (Decimal(duration_minutes) / Decimal("60")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalize_status(billing_type: str, invoice_id: int | None, requested_status: str | None) -> str:
    if invoice_id:
        return "invoiced"
    if billing_type in {"non_billable", "no_charge"}:
        return "non_billable"
    if requested_status in {"draft", "billable"}:
        return requested_status
    return "billable"


def _normalize_billing_type(billing_type: str, invoice_id: int | None) -> str:
    if invoice_id:
        return "invoiced"
    return billing_type


def _serialize(entry: TimeEntry) -> TimeEntryResponse:
    case = getattr(entry, "case", None)
    client = getattr(entry, "client", None) or getattr(case, "client", None)
    staff = getattr(entry, "user", None)
    invoice = getattr(entry, "invoice", None)
    return TimeEntryResponse(
        id=entry.id,
        organization_id=entry.organization_id,
        case_id=entry.case_id,
        client_id=entry.client_id,
        user_id=entry.user_id,
        invoice_id=entry.invoice_id,
        description=entry.description,
        start_time=entry.start_time,
        end_time=entry.end_time,
        duration_minutes=entry.duration_minutes,
        billing_type=entry.billing_type,
        hourly_rate=entry.hourly_rate,
        amount=entry.amount,
        status=entry.status,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        case_title=getattr(case, "title", None),
        case_display_number=f"C-{case.id}" if getattr(case, "id", None) else None,
        client_name=getattr(client, "name", None),
        staff_name=getattr(staff, "name", None),
        invoice_number=getattr(invoice, "invoice_number", None),
    )


async def _get_time_entry_or_404(db: AsyncSession, org_id: int, entry_id: int) -> TimeEntry:
    entry = await db.scalar(
        select(TimeEntry)
        .where(TimeEntry.id == entry_id, TimeEntry.organization_id == org_id)
        .options(
            selectinload(TimeEntry.case).selectinload(Case.client),
            selectinload(TimeEntry.client),
            selectinload(TimeEntry.user),
            selectinload(TimeEntry.invoice),
        )
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time entry not found")
    return entry


async def _validate_related_records(
    db: AsyncSession,
    *,
    org_id: int,
    case_id: int | None,
    client_id: int | None,
    user_id: int,
    invoice_id: int | None,
) -> tuple[Case | None, Client | None, User, Invoice | None]:
    case = None
    if case_id is not None:
        case = await db.scalar(select(Case).where(Case.id == case_id, Case.organization_id == org_id))
        if not case:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case must belong to your organization")

    client = None
    if client_id is not None:
        client = await db.scalar(select(Client).where(Client.id == client_id, Client.organization_id == org_id))
        if not client:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client must belong to your organization")

    if case and client and case.client_id != client.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case does not belong to client")

    if case and client is None:
        client = await db.scalar(select(Client).where(Client.id == case.client_id, Client.organization_id == org_id))

    user = await db.scalar(select(User).where(User.id == user_id, User.organization_id == org_id))
    if not user or user.role.value == "client":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Staff user must belong to your organization")

    invoice = None
    if invoice_id is not None:
        invoice = await db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == org_id))
        if not invoice:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice must belong to your organization")
        if case and invoice.case_id and invoice.case_id != case.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice does not belong to case")
        resolved_client_id = client.id if client else case.client_id if case else None
        if resolved_client_id and invoice.client_id != resolved_client_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice does not belong to client")

    return case, client, user, invoice


def _resolve_duration_and_amount(
    *,
    start_time: datetime | None,
    end_time: datetime | None,
    duration_minutes: int | None,
    billing_type: str,
    hourly_rate: Decimal | None,
) -> tuple[int | None, Decimal | None, Decimal]:
    if start_time and not end_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End time is required when start time is set")
    if end_time and not start_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start time is required when end time is set")
    if start_time and end_time:
        if end_time <= start_time:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End time must be after start time")
        duration_minutes = max(1, int((end_time - start_time).total_seconds() // 60))
    if duration_minutes is None or duration_minutes <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duration must be positive")

    normalized_rate = _round_money(Decimal(str(hourly_rate))) if hourly_rate is not None else None
    if billing_type in {"non_billable", "no_charge"}:
        return duration_minutes, None if billing_type == "non_billable" else normalized_rate, ZERO
    if normalized_rate is None or normalized_rate < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hourly rate is required for billable entries")
    amount = _round_money(_entry_hours(duration_minutes) * normalized_rate)
    return duration_minutes, normalized_rate, amount


@router.get("", response_model=TimeEntryListResponse)
async def list_time_entries(
    search: str | None = Query(default=None),
    date_range: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    case_id: int | None = Query(default=None),
    billing_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort_by: str = Query(default="newest"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED)),
):
    filters = [TimeEntry.organization_id == current_user.organization_id]
    if case_id is not None:
        filters.append(TimeEntry.case_id == case_id)
    if billing_type:
        filters.append(TimeEntry.billing_type == billing_type.strip().lower())
    if status_filter:
        filters.append(TimeEntry.status == status_filter.strip().lower())

    effective_start = start_date
    effective_end = end_date
    now = datetime.now(timezone.utc)
    if date_range and not start_date and not end_date:
        normalized = date_range.strip().lower()
        if normalized == "today":
            effective_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            effective_end = now
        elif normalized == "last_7_days":
            effective_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
            effective_end = now
        elif normalized == "last_30_days":
            effective_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=29)
            effective_end = now
        elif normalized == "this_month":
            effective_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            effective_end = now

    time_anchor = func.coalesce(TimeEntry.start_time, TimeEntry.created_at)
    if effective_start is not None:
        filters.append(time_anchor >= effective_start)
    if effective_end is not None:
        filters.append(time_anchor <= effective_end)

    text_filter = None
    if search:
        term = f"%{search.strip()}%"
        if term != "%%":
            text_filter = or_(
                TimeEntry.description.ilike(term),
                Case.title.ilike(term),
                Client.name.ilike(term),
                User.name.ilike(term),
                cast(TimeEntry.id, String).ilike(term),
            )
            filters.append(text_filter)

    base_query = (
        select(TimeEntry)
        .outerjoin(Case, Case.id == TimeEntry.case_id)
        .outerjoin(Client, Client.id == TimeEntry.client_id)
        .outerjoin(User, User.id == TimeEntry.user_id)
        .where(and_(*filters))
        .options(
            selectinload(TimeEntry.case).selectinload(Case.client),
            selectinload(TimeEntry.client),
            selectinload(TimeEntry.user),
            selectinload(TimeEntry.invoice),
        )
    )

    sort_map = {
        "oldest": TimeEntry.created_at.asc(),
        "amount_desc": TimeEntry.amount.desc(),
        "amount_asc": TimeEntry.amount.asc(),
        "duration_desc": TimeEntry.duration_minutes.desc(),
        "duration_asc": TimeEntry.duration_minutes.asc(),
        "type": TimeEntry.billing_type.asc(),
        "start_time": TimeEntry.start_time.desc().nullslast(),
        "newest": TimeEntry.created_at.desc(),
    }
    order_clause = sort_map.get(sort_by, TimeEntry.created_at.desc())
    total = int((await db.scalar(select(func.count(TimeEntry.id)).select_from(TimeEntry).outerjoin(Case, Case.id == TimeEntry.case_id).outerjoin(Client, Client.id == TimeEntry.client_id).outerjoin(User, User.id == TimeEntry.user_id).where(and_(*filters)))) or 0)
    rows = await db.scalars(base_query.order_by(order_clause, TimeEntry.id.desc()).offset((page - 1) * per_page).limit(per_page))
    total_pages = max(1, (total + per_page - 1) // per_page) if per_page else 1
    return TimeEntryListResponse(items=[_serialize(row) for row in rows.all()], total=total, page=page, per_page=per_page, total_pages=total_pages)


@router.post("", response_model=TimeEntryResponse)
async def create_time_entry(
    payload: TimeEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED)),
):
    user_id = payload.user_id or current_user.id
    case, client, _, invoice = await _validate_related_records(
        db,
        org_id=current_user.organization_id,
        case_id=payload.case_id,
        client_id=payload.client_id,
        user_id=user_id,
        invoice_id=payload.invoice_id,
    )
    billing_type = _normalize_billing_type(payload.billing_type, payload.invoice_id)
    duration_minutes, hourly_rate, amount = _resolve_duration_and_amount(
        start_time=payload.start_time,
        end_time=payload.end_time,
        duration_minutes=payload.duration_minutes,
        billing_type=billing_type,
        hourly_rate=payload.hourly_rate,
    )
    now = datetime.now(timezone.utc)
    entry = TimeEntry(
        organization_id=current_user.organization_id,
        case_id=case.id if case else None,
        client_id=client.id if client else case.client_id if case else None,
        user_id=user_id,
        invoice_id=invoice.id if invoice else None,
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        duration_minutes=duration_minutes,
        billing_type=billing_type,
        hourly_rate=hourly_rate,
        amount=amount,
        status=_normalize_status(billing_type, invoice.id if invoice else None, payload.status),
        created_at=now,
        updated_at=now,
    )
    db.add(entry)
    await db.flush()
    if case:
        await create_case_timeline_event(
            db,
            organization_id=current_user.organization_id,
            case_id=case.id,
            actor_id=current_user.id,
            event_type="time_entry_added",
            title="Time entry added",
            metadata_json={"time_entry_id": entry.id},
        )
    await db.commit()
    return _serialize(await _get_time_entry_or_404(db, current_user.organization_id, entry.id))


@router.get("/{entry_id}", response_model=TimeEntryResponse)
async def get_time_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED)),
):
    return _serialize(await _get_time_entry_or_404(db, current_user.organization_id, entry_id))


@router.patch("/{entry_id}", response_model=TimeEntryResponse)
async def update_time_entry(
    entry_id: int,
    payload: TimeEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED)),
):
    entry = await _get_time_entry_or_404(db, current_user.organization_id, entry_id)
    if entry.invoice_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Linked invoice time entries cannot be edited")

    updates = payload.model_dump(exclude_unset=True)
    resolved_case_id = updates.get("case_id", entry.case_id)
    resolved_client_id = updates.get("client_id", entry.client_id)
    resolved_user_id = updates.get("user_id", entry.user_id)
    resolved_invoice_id = updates.get("invoice_id", entry.invoice_id)

    case, client, _, invoice = await _validate_related_records(
        db,
        org_id=current_user.organization_id,
        case_id=resolved_case_id,
        client_id=resolved_client_id,
        user_id=resolved_user_id,
        invoice_id=resolved_invoice_id,
    )
    billing_type = _normalize_billing_type(updates.get("billing_type", entry.billing_type), resolved_invoice_id)
    duration_minutes, hourly_rate, amount = _resolve_duration_and_amount(
        start_time=updates.get("start_time", entry.start_time),
        end_time=updates.get("end_time", entry.end_time),
        duration_minutes=updates.get("duration_minutes", entry.duration_minutes),
        billing_type=billing_type,
        hourly_rate=updates.get("hourly_rate", entry.hourly_rate),
    )

    entry.case_id = case.id if case else None
    entry.client_id = client.id if client else case.client_id if case else None
    entry.user_id = resolved_user_id
    entry.invoice_id = invoice.id if invoice else None
    entry.description = updates.get("description", entry.description)
    entry.start_time = updates.get("start_time", entry.start_time)
    entry.end_time = updates.get("end_time", entry.end_time)
    entry.duration_minutes = duration_minutes
    entry.billing_type = billing_type
    entry.hourly_rate = hourly_rate
    entry.amount = amount
    entry.status = _normalize_status(billing_type, entry.invoice_id, updates.get("status", entry.status))
    entry.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _serialize(await _get_time_entry_or_404(db, current_user.organization_id, entry_id))


@router.delete("/{entry_id}")
async def delete_time_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED)),
):
    entry = await _get_time_entry_or_404(db, current_user.organization_id, entry_id)
    linked_line_item = await db.scalar(select(InvoiceLineItem.id).where(InvoiceLineItem.organization_id == current_user.organization_id, InvoiceLineItem.time_entry_id == entry.id))
    if entry.invoice_id or linked_line_item:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Linked invoice time entries cannot be deleted")
    await db.delete(entry)
    await db.commit()
    return {"ok": True}
