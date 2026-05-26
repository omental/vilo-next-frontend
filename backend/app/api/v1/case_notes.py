from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import role_guard
from app.db.session import get_db
from app.models.case import Case
from app.models.case_note import CaseNote
from app.models.user import User
from app.schemas.case_note import CaseNoteCreate, CaseNoteResponse, CaseNoteUpdate
from app.services.timeline import create_case_timeline_event

router = APIRouter(prefix="/cases/{case_id}/notes", tags=["case-notes"])
ALLOWED_STAFF = ["partner", "admin", "lawyer", "paralegal"]
VALID_VISIBILITY = {"internal", "client_visible"}


async def get_case_or_404(db: AsyncSession, case_id: int, organization_id: int) -> Case:
    case = await db.scalar(select(Case).where(Case.id == case_id, Case.organization_id == organization_id))
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return case


def serialize(note: CaseNote) -> CaseNoteResponse:
    return CaseNoteResponse(
        id=note.id,
        organization_id=note.organization_id,
        case_id=note.case_id,
        created_by=note.created_by,
        note=note.note,
        visibility=note.visibility,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def validate_visibility(value: str | None):
    if value is not None and value not in VALID_VISIBILITY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid visibility")


@router.post("", response_model=CaseNoteResponse)
async def create_case_note(
    case_id: int,
    payload: CaseNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    case = await get_case_or_404(db, case_id, current_user.organization_id)
    validate_visibility(payload.visibility)

    now = datetime.now(timezone.utc)
    note = CaseNote(
        organization_id=current_user.organization_id,
        case_id=case.id,
        created_by=current_user.id,
        note=payload.note,
        visibility=payload.visibility,
        created_at=now,
        updated_at=now,
    )
    db.add(note)
    await db.flush()

    await create_case_timeline_event(
        db,
        organization_id=current_user.organization_id,
        case_id=case.id,
        actor_id=current_user.id,
        event_type="note_added",
        title="Case note added",
        metadata_json={"note_id": note.id, "visibility": note.visibility},
    )

    await db.commit()
    await db.refresh(note)
    return serialize(note)


@router.get("", response_model=list[CaseNoteResponse])
async def list_case_notes(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    await get_case_or_404(db, case_id, current_user.organization_id)
    rows = await db.scalars(
        select(CaseNote)
        .where(CaseNote.case_id == case_id, CaseNote.organization_id == current_user.organization_id)
        .order_by(CaseNote.created_at.desc())
    )
    return [serialize(note) for note in rows.all()]


@router.get("/{note_id}", response_model=CaseNoteResponse)
async def get_case_note(
    case_id: int,
    note_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    await get_case_or_404(db, case_id, current_user.organization_id)
    note = await db.scalar(
        select(CaseNote).where(
            CaseNote.id == note_id,
            CaseNote.case_id == case_id,
            CaseNote.organization_id == current_user.organization_id,
        )
    )
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case note not found")
    return serialize(note)


@router.patch("/{note_id}", response_model=CaseNoteResponse)
async def update_case_note(
    case_id: int,
    note_id: int,
    payload: CaseNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    case = await get_case_or_404(db, case_id, current_user.organization_id)
    note = await db.scalar(
        select(CaseNote).where(
            CaseNote.id == note_id,
            CaseNote.case_id == case.id,
            CaseNote.organization_id == current_user.organization_id,
        )
    )
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case note not found")

    updates = payload.model_dump(exclude_unset=True)
    validate_visibility(updates.get("visibility"))
    for key, value in updates.items():
        setattr(note, key, value)
    note.updated_at = datetime.now(timezone.utc)

    await create_case_timeline_event(
        db,
        organization_id=current_user.organization_id,
        case_id=case.id,
        actor_id=current_user.id,
        event_type="note_updated",
        title="Case note updated",
        metadata_json={"note_id": note.id},
    )

    await db.commit()
    await db.refresh(note)
    return serialize(note)


@router.delete("/{note_id}")
async def delete_case_note(
    case_id: int,
    note_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_guard(ALLOWED_STAFF)),
):
    case = await get_case_or_404(db, case_id, current_user.organization_id)
    note = await db.scalar(
        select(CaseNote).where(
            CaseNote.id == note_id,
            CaseNote.case_id == case.id,
            CaseNote.organization_id == current_user.organization_id,
        )
    )
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case note not found")

    await create_case_timeline_event(
        db,
        organization_id=current_user.organization_id,
        case_id=case.id,
        actor_id=current_user.id,
        event_type="note_deleted",
        title="Case note deleted",
        metadata_json={"note_id": note.id},
    )

    await db.delete(note)
    await db.commit()
    return {"ok": True}
