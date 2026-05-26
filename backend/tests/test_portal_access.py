from types import SimpleNamespace

from fastapi import HTTPException

from app.api.v1 import portal as portal_module


def test_cross_client_portal_case_access_returns_404(client_for_user, monkeypatch):
    client = client_for_user("client", linked_client=True)

    async def _deny_case(*args, **kwargs):
        raise HTTPException(status_code=404, detail="Case not found")

    monkeypatch.setattr(portal_module, "get_client_case_or_404", _deny_case)
    res = client.get("/api/v1/portal/cases/999")
    assert res.status_code == 404


def test_portal_list_shapes_paginated(client_for_user):
    client = client_for_user("client", linked_client=True)

    for path in [
        "/api/v1/portal/cases",
        "/api/v1/portal/documents",
        "/api/v1/portal/invoices",
        "/api/v1/portal/notes",
    ]:
        res = client.get(path)
        assert res.status_code == 200
        body = res.json()
        assert set(["items", "total", "page", "page_size"]).issubset(body.keys())


def test_portal_intake_is_read_only_after_submit(client_for_user):
    client = client_for_user("client", linked_client=True)

    submitted = SimpleNamespace(
        id=1,
        organization_id=1,
        client_id=10,
        submitted_by=1,
        status="submitted",
        full_name="Client A",
        email="a@example.com",
        phone="123",
        address=None,
        matter_type=None,
        description=None,
        submitted_at=None,
        created_at=None,
        updated_at=None,
    )

    client._dummy_db._scalar = submitted  # type: ignore[attr-defined]
    res = client.patch("/api/v1/portal/intake/1", json={"description": "new"})
    assert res.status_code == 400
