import pytest


STAFF_ROLES = ["partner", "admin", "lawyer", "paralegal"]


@pytest.mark.parametrize("role", STAFF_ROLES)
def test_portal_blocked_for_staff_roles(client_for_user, role):
    client = client_for_user(role)
    res = client.get("/api/v1/portal/me")
    assert res.status_code == 403


def test_portal_allowed_for_linked_client(client_for_user):
    client = client_for_user("client", linked_client=True)
    res = client.get("/api/v1/portal/me")
    assert res.status_code == 200


def test_portal_blocked_for_unlinked_client(client_for_user):
    client = client_for_user("client", linked_client=False)
    res = client.get("/api/v1/portal/me")
    assert res.status_code == 403


@pytest.mark.parametrize("role", ["client"])
def test_staff_endpoints_block_client_role(client_for_user, role):
    client = client_for_user(role)
    assert client.get("/api/v1/clients").status_code == 403
    assert client.get("/api/v1/cases").status_code == 403
    assert client.get("/api/v1/documents").status_code == 403
    assert client.get("/api/v1/invoices").status_code == 403
    assert client.get("/api/v1/trust/accounts").status_code == 403
    assert client.get("/api/v1/reports/dashboard-summary").status_code == 403
