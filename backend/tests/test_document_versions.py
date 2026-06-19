from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import AsyncIterator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import deps as deps_module
from app.api.v1 import documents as documents_module
from app.main import app
from app.models.enums import RecordStatus, UserRole


@dataclass
class DummyUser:
    id: int
    organization_id: int
    name: str
    email: str
    role: UserRole
    status: RecordStatus = RecordStatus.active
    created_at: datetime = datetime.now(timezone.utc)
    updated_at: datetime = datetime.now(timezone.utc)


class DocsVersionDBStub:
    def __init__(self, scalar_values=None, scalars_values=None):
        self.scalar_values = list(scalar_values or [])
        self.scalars_values = list(scalars_values or [])
        self.added = []

    async def scalar(self, query, *args, **kwargs):
        assert "organization_id" in str(query)
        if self.scalar_values:
            return self.scalar_values.pop(0)
        return None

    async def scalars(self, query, *args, **kwargs):
        assert "organization_id" in str(query)
        rows = self.scalars_values.pop(0) if self.scalars_values else []

        class _Rows:
            def __init__(self, values):
                self._values = values

            def all(self):
                return self._values

        return _Rows(rows)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def refresh(self, obj):
        return None


def _doc_obj(doc_id=51, org_id=1, path="/tmp/original.pdf"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=doc_id,
        organization_id=org_id,
        case_id=None,
        client_id=None,
        uploaded_by=99,
        title="Engagement Letter",
        description="Doc",
        file_name="original.pdf",
        file_path=path,
        file_type="application/pdf",
        file_size=120,
        category="general",
        visibility="internal",
        version=1,
        version_source="upload",
        version_note=None,
        created_at=now,
        updated_at=now,
    )


def _version_obj(version_id=8, doc_id=51, org_id=1):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=version_id,
        document_id=doc_id,
        organization_id=org_id,
        file_name="original.pdf",
        file_path="/tmp/original.pdf",
        file_type="application/pdf",
        file_size=120,
        version_number=1,
        uploaded_by=10,
        source="upload",
        notes="Initial",
        created_at=now,
    )


def build_client(role: str, db: DocsVersionDBStub, org_id: int = 1):
    user = DummyUser(id=10, organization_id=org_id, name=f"{role} user", email="u@example.com", role=UserRole(role))

    async def _get_current_user():
        return user

    async def _get_db() -> AsyncIterator[DocsVersionDBStub]:
        yield db

    app.dependency_overrides[deps_module.get_current_user] = _get_current_user
    app.dependency_overrides[deps_module.get_db] = _get_db
    return TestClient(app)


def cleanup(client: TestClient):
    client.close()
    app.dependency_overrides.clear()


def test_replace_document_updates_latest_and_keeps_previous_metadata(monkeypatch):
    with TemporaryDirectory() as tmpdir:
        original_path = Path(tmpdir) / "original.pdf"
        original_path.write_bytes(b"old")
        db = DocsVersionDBStub(scalar_values=[_doc_obj(path=str(original_path))])
        client = build_client("admin", db)
        monkeypatch.setattr(documents_module, "STORAGE_ROOT", Path(tmpdir))
        try:
            res = client.post(
                "/api/v1/documents/51/replace",
                data={"notes": "Replaced after review"},
                files={"file": ("replacement.pdf", b"%PDF-1.4 replacement", "application/pdf")},
            )
            assert res.status_code == 200
            body = res.json()
            assert body["file_name"] == "replacement.pdf"
            assert body["version"] == 2
            version_rows = [row for row in db.added if row.__class__.__name__ == "DocumentVersion"]
            assert len(version_rows) == 1
            assert version_rows[0].file_name == "original.pdf"
            assert version_rows[0].version_number == 1
        finally:
            cleanup(client)


def test_document_versions_list_is_org_scoped():
    db = DocsVersionDBStub(scalar_values=[_doc_obj()], scalars_values=[[_version_obj()]])
    client = build_client("lawyer", db)
    try:
        res = client.get("/api/v1/documents/51/versions")
        assert res.status_code == 200
        body = res.json()
        assert len(body) == 1
        assert body[0]["version_number"] == 1
        assert body[0]["source"] == "upload"
        assert "file_path" not in body[0]
    finally:
        cleanup(client)


def test_cross_org_document_versions_access_blocked():
    db = DocsVersionDBStub(scalar_values=[None])
    client = build_client("partner", db)
    try:
        res = client.get("/api/v1/documents/999/versions")
        assert res.status_code == 404
    finally:
        cleanup(client)


def test_client_role_cannot_replace_document():
    db = DocsVersionDBStub()
    client = build_client("client", db)
    try:
        res = client.post(
            "/api/v1/documents/51/replace",
            files={"file": ("replacement.pdf", b"%PDF", "application/pdf")},
        )
        assert res.status_code == 403
    finally:
        cleanup(client)


def test_docx_editable_content_returns_extracted_text(monkeypatch):
    with TemporaryDirectory() as tmpdir:
        doc_path = Path(tmpdir) / "editable.docx"
        monkeypatch.setattr(documents_module, "extract_docx_text", lambda _path: "Paragraph one\nParagraph two")
        db = DocsVersionDBStub(
            scalar_values=[
                _doc_obj(path=str(doc_path)),
            ]
        )
        doc = db.scalar_values[0]
        doc.file_name = "editable.docx"
        doc.file_type = documents_module.DOCX_MIME_TYPE
        client = build_client("lawyer", db)
        try:
            res = client.get("/api/v1/documents/51/editable-content")
            assert res.status_code == 200
            body = res.json()
            assert body["editable"] is True
            assert body["mode"] == "docx_text"
            assert body["content"] == "Paragraph one\nParagraph two"
            assert "file_path" not in body
        finally:
            cleanup(client)


def test_pdf_editable_content_returns_unsupported():
    db = DocsVersionDBStub(scalar_values=[_doc_obj()])
    client = build_client("admin", db)
    try:
        res = client.get("/api/v1/documents/51/editable-content")
        assert res.status_code == 200
        body = res.json()
        assert body["editable"] is False
        assert "PDF editing will be added later" in body["reason"]
        assert "file_path" not in body
    finally:
        cleanup(client)


def test_client_role_cannot_access_docx_editable_content():
    db = DocsVersionDBStub()
    client = build_client("client", db)
    try:
        res = client.get("/api/v1/documents/51/editable-content")
        assert res.status_code == 403
    finally:
        cleanup(client)


@pytest.mark.asyncio
async def test_replace_keeps_old_file_and_versions_download_previous_binary(tmp_path):
    monkey = pytest.MonkeyPatch()
    monkey.setattr(documents_module, "STORAGE_ROOT", tmp_path)
    old_path = tmp_path / "org1" / "original.pdf"
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(b"OLD_BINARY")

    doc = _doc_obj(path=str(old_path))
    db = DocsVersionDBStub()
    user = DummyUser(id=10, organization_id=1, name="Admin", email="a@example.com", role=UserRole.admin)

    class _Rows:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    version_rows = []

    async def scalar_side_effect(query, *args, **kwargs):
        q = str(query)
        if "document_versions.id" in q:
            return version_rows[0] if version_rows else None
        if "documents.id" in q:
            return doc
        return None

    db.scalar = scalar_side_effect  # type: ignore[assignment]

    async def scalars_side_effect(query, *args, **kwargs):
        if "document_versions" in str(query):
            return _Rows(version_rows)
        return _Rows([])

    db.scalars = scalars_side_effect  # type: ignore[assignment]

    def add_side_effect(obj):
        db.added.append(obj)
        if obj.__class__.__name__ == "DocumentVersion":
            version_rows.append(obj)

    db.add = add_side_effect  # type: ignore[assignment]

    upload = SimpleNamespace(filename="replacement.pdf", content_type="application/pdf")

    async def upload_read():
        return b"NEW_BINARY"

    upload.read = upload_read  # type: ignore[assignment]

    replaced = await documents_module.replace_document(
        document_id=51,
        file=upload,
        notes="replacement note",
        request=None,
        db=db,
        current_user=user,
    )
    assert replaced.file_name == "replacement.pdf"
    assert replaced.version == 2
    assert old_path.exists()
    assert old_path.read_bytes() == b"OLD_BINARY"
    assert version_rows[0].file_path == str(old_path)

    latest_download = await documents_module.download_document(document_id=51, db=db, current_user=user)
    assert latest_download.filename == "replacement.pdf"

    version_download = await documents_module.download_document_version(
        document_id=51,
        version_id=version_rows[0].id,
        db=db,
        current_user=user,
    )
    assert version_download.filename == "original.pdf"
    monkey.undo()


@pytest.mark.asyncio
async def test_save_docx_edit_creates_new_version_and_keeps_original(tmp_path):
    monkey = pytest.MonkeyPatch()
    monkey.setattr(documents_module, "STORAGE_ROOT", tmp_path)

    original_bytes = documents_module.render_docx_bytes("Original version")
    old_path = tmp_path / "org1" / "editable.docx"
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(original_bytes)

    doc = _doc_obj(path=str(old_path))
    doc.file_name = "editable.docx"
    doc.file_type = documents_module.DOCX_MIME_TYPE
    db = DocsVersionDBStub()
    user = DummyUser(id=10, organization_id=1, name="Admin", email="a@example.com", role=UserRole.admin)

    version_rows = []

    async def scalar_side_effect(query, *args, **kwargs):
        q = str(query)
        if "documents.id" in q:
            return doc
        return None

    db.scalar = scalar_side_effect  # type: ignore[assignment]

    def add_side_effect(obj):
        db.added.append(obj)
        if obj.__class__.__name__ == "DocumentVersion":
            version_rows.append(obj)

    db.add = add_side_effect  # type: ignore[assignment]

    updated = await documents_module.save_document_editable_content(
        document_id=51,
        payload=documents_module.DocumentEditableContentUpdate(content="Edited content", version_note="Cleaned up clauses"),
        request=SimpleNamespace(client=None, headers={}),
        db=db,
        current_user=user,
    )

    assert updated.version == 2
    assert updated.version_source == "content_edit"
    assert updated.version_note == "Cleaned up clauses"
    assert len(version_rows) == 1
    assert version_rows[0].file_name == "editable.docx"
    assert version_rows[0].version_number == 1
    assert version_rows[0].source == "upload"
    assert Path(version_rows[0].file_path).read_bytes() == original_bytes
    assert Path(doc.file_path).exists()
    assert doc.file_path != str(old_path)
    assert documents_module.extract_docx_text(doc.file_path) == "Edited content"
    monkey.undo()


def test_cross_org_docx_edit_access_blocked():
    db = DocsVersionDBStub(scalar_values=[None])
    client = build_client("partner", db)
    try:
        res = client.post("/api/v1/documents/999/editable-content", json={"content": "x", "version_note": "note"})
        assert res.status_code == 404
    finally:
        cleanup(client)


def test_client_role_cannot_save_docx_edit():
    db = DocsVersionDBStub()
    client = build_client("client", db)
    try:
        res = client.post("/api/v1/documents/51/editable-content", json={"content": "x"})
        assert res.status_code == 403
    finally:
        cleanup(client)


@pytest.mark.asyncio
async def test_download_historical_version_missing_file_returns_404():
    db = DocsVersionDBStub()
    user = DummyUser(id=10, organization_id=1, name="Admin", email="a@example.com", role=UserRole.admin)
    doc = _doc_obj(path="/tmp/current.pdf")
    missing_version = _version_obj()
    missing_version.file_path = "/tmp/does-not-exist-vilo-version.bin"

    async def scalar_side_effect(query, *args, **kwargs):
        q = str(query)
        if "document_versions.id" in q:
            return missing_version
        if "documents.id" in q:
            return doc
        return None

    db.scalar = scalar_side_effect  # type: ignore[assignment]

    with pytest.raises(HTTPException) as exc:
        await documents_module.download_document_version(
            document_id=51,
            version_id=missing_version.id,
            db=db,
            current_user=user,
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "Stored file not found"
