from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.cases import validate_case_required_fields
from app.models.case import Case, CaseStatus
from app.schemas.case import CaseCreate, CaseUpdate
from app.schemas.invoice import InvoiceCreate
from app.services.document_storage import resolve_stored_file


def test_invoice_create_defaults_to_jmd_and_allows_no_case():
    payload = InvoiceCreate(client_id=4, issue_date=date(2026, 7, 24))
    assert payload.currency == "JMD"
    assert payload.case_id is None


def test_case_draft_allows_incomplete_fields_and_preserves_expected_date():
    payload = CaseCreate(status=CaseStatus.draft, expected_completion_date=date(2026, 12, 1))
    assert payload.title is None
    assert payload.client_id is None
    assert payload.expected_completion_date == date(2026, 12, 1)


def test_active_case_requires_title_and_client():
    with pytest.raises(ValidationError):
        CaseCreate(status=CaseStatus.active)


def test_complete_active_case_is_allowed():
    payload = CaseCreate(status=CaseStatus.active, title="Estate matter", client_id=7)
    assert payload.status == CaseStatus.active


def test_active_case_without_title_is_rejected():
    with pytest.raises(HTTPException) as exc:
        validate_case_required_fields(CaseStatus.active, None, 7)
    assert exc.value.status_code == 422
    assert exc.value.detail == "Title is required to complete a case"


def test_active_case_without_client_is_rejected():
    with pytest.raises(HTTPException) as exc:
        validate_case_required_fields(CaseStatus.active, "Estate matter", None)
    assert exc.value.status_code == 422
    assert exc.value.detail == "Client is required to complete a case"


def test_incomplete_draft_cannot_be_submitted_as_active():
    with pytest.raises(HTTPException):
        validate_case_required_fields(CaseStatus.active, None, None)


@pytest.mark.parametrize(
    ("title", "client_id"),
    [(None, 7), ("Estate matter", None), ("   ", 7)],
)
def test_clearing_required_fields_from_active_case_is_rejected(title, client_id):
    with pytest.raises(HTTPException):
        validate_case_required_fields(CaseStatus.active, title, client_id)


def test_case_model_declares_database_integrity_constraint():
    constraints = {constraint.name: str(constraint.sqltext) for constraint in Case.__table__.constraints if constraint.name}
    assert constraints["ck_cases_non_draft_required_fields"] == (
        "status = 'draft' OR (title IS NOT NULL AND client_id IS NOT NULL)"
    )


def test_expected_completion_date_can_be_cleared():
    update = CaseUpdate(expected_completion_date=None)
    assert update.model_dump(exclude_unset=True) == {"expected_completion_date": None}


def test_storage_resolver_accepts_file_inside_root_and_blocks_traversal(tmp_path):
    approved = tmp_path / "documents"
    approved.mkdir()
    stored = approved / "brief.pdf"
    stored.write_bytes(b"brief")
    assert resolve_stored_file(str(stored), approved) == stored

    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    with pytest.raises(HTTPException) as exc:
        resolve_stored_file(str(outside), approved)
    assert exc.value.status_code == 404
