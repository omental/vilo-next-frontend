from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import portal_messages as portal_messages_module


STAFF_ROLES = ["partner", "admin", "lawyer", "paralegal"]


def test_client_blocked_from_staff_conversations(client_for_user):
    client = client_for_user("client")
    res = client.get("/api/v1/conversations")
    assert res.status_code == 403


@pytest.mark.parametrize("role", STAFF_ROLES)
def test_staff_allowed_on_conversations_list(client_for_user, role):
    client = client_for_user(role)
    res = client.get("/api/v1/conversations")
    assert res.status_code == 200


@pytest.mark.parametrize("role", STAFF_ROLES)
def test_staff_blocked_from_portal_messages_routes(client_for_user, role):
    client = client_for_user(role)
    assert client.get("/api/v1/portal/messages/conversations").status_code == 403
    assert client.get("/api/v1/portal/messages/conversations/1").status_code == 403


def test_linked_client_allowed_on_portal_messages_conversations(client_for_user, monkeypatch):
    client = client_for_user("client", linked_client=True)

    async def _portal_client(_db, _user):
        return SimpleNamespace(id=10, organization_id=1, user_id=1)

    monkeypatch.setattr(portal_messages_module, "get_portal_client", _portal_client)
    res = client.get("/api/v1/portal/messages/conversations")
    assert res.status_code == 200


def test_unlinked_client_blocked_from_portal_messages(client_for_user, monkeypatch):
    client = client_for_user("client", linked_client=False)

    async def _deny(_db, _user):
        raise HTTPException(status_code=403, detail="Client profile not linked")

    monkeypatch.setattr(portal_messages_module, "get_portal_client", _deny)
    res = client.get("/api/v1/portal/messages/conversations")
    assert res.status_code == 403


def test_client_cannot_access_internal_conversation_through_portal(client_for_user, monkeypatch):
    client = client_for_user("client", linked_client=True)

    async def _portal_client(_db, _user):
        return SimpleNamespace(id=10, organization_id=1, user_id=1)

    async def _deny_conv(*args, **kwargs):
        raise HTTPException(status_code=404, detail="Conversation not found")

    monkeypatch.setattr(portal_messages_module, "get_portal_client", _portal_client)
    monkeypatch.setattr(portal_messages_module, "get_allowed_conversation", _deny_conv)

    res = client.get("/api/v1/portal/messages/conversations/123")
    assert res.status_code == 404


def test_client_cannot_access_other_clients_conversation(client_for_user, monkeypatch):
    client = client_for_user("client", linked_client=True)

    async def _portal_client(_db, _user):
        return SimpleNamespace(id=10, organization_id=1, user_id=1)

    async def _deny_conv(*args, **kwargs):
        raise HTTPException(status_code=404, detail="Conversation not found")

    monkeypatch.setattr(portal_messages_module, "get_portal_client", _portal_client)
    monkeypatch.setattr(portal_messages_module, "get_allowed_conversation", _deny_conv)

    res = client.get("/api/v1/portal/messages/conversations/999")
    assert res.status_code == 404


def test_sender_must_be_participant_before_posting_message(client_for_user):
    client = client_for_user("lawyer")
    res = client.post("/api/v1/conversations/77/messages", json={"body": "hello"})
    assert res.status_code == 403


def test_cross_org_conversation_access_hidden_or_blocked(client_for_user):
    client = client_for_user("partner")
    # When conversation is not in participant scope, API should not allow access.
    res = client.get("/api/v1/conversations/98765")
    assert res.status_code in (403, 404)
