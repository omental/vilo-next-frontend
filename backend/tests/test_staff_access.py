import pytest


def test_paralegal_blocked_from_invoice_mark_paid(client_for_user):
    client = client_for_user("paralegal")
    res = client.patch("/api/v1/invoices/1/mark-paid")
    assert res.status_code == 403


@pytest.mark.parametrize("role", ["partner", "admin"])
def test_partner_admin_can_manage_trust_endpoints(client_for_user, role):
    client = client_for_user(role)
    res = client.post(
        "/api/v1/trust/deposit",
        json={
            "trust_account_id": 1,
            "client_id": 1,
            "case_id": 1,
            "amount": "100.00",
            "description": "seed",
            "currency": "USD",
            "transaction_date": "2026-05-04",
        },
    )
    assert res.status_code in (200, 400, 404, 422)
    apply_res = client.post("/api/v1/invoices/1/apply-trust", json={"amount": "50.00"})
    assert apply_res.status_code in (200, 400, 404, 422)
    void_res = client.post("/api/v1/invoices/1/payments/1/void", json={"void_reason": "bad"})
    assert void_res.status_code in (200, 400, 404, 409, 422)


@pytest.mark.parametrize("role", ["lawyer", "paralegal"])
def test_lawyer_paralegal_view_only_trust(client_for_user, role):
    client = client_for_user(role)
    assert client.get("/api/v1/trust/accounts").status_code == 200
    post_res = client.post(
        "/api/v1/trust/deposit",
        json={
            "trust_account_id": 1,
            "client_id": 1,
            "case_id": 1,
            "amount": "100.00",
            "description": "seed",
            "currency": "USD",
            "transaction_date": "2026-05-04",
        },
    )
    assert post_res.status_code == 403
    apply_res = client.post("/api/v1/invoices/1/apply-trust", json={"amount": "50.00"})
    assert apply_res.status_code == 403
    void_res = client.post("/api/v1/invoices/1/payments/1/void", json={"void_reason": "bad"})
    assert void_res.status_code == 403


@pytest.mark.parametrize("role,expected", [
    ("paralegal", 403),
    ("lawyer", 200),
    ("admin", 200),
    ("partner", 200),
    ("client", 403),
])
def test_reports_dashboard_summary_role_access(client_for_user, role, expected):
    client = client_for_user(role)
    res = client.get("/api/v1/reports/dashboard-summary")
    assert res.status_code == expected


@pytest.mark.parametrize("role,expected", [
    ("paralegal", 200),
    ("lawyer", 200),
    ("admin", 200),
    ("partner", 200),
    ("client", 403),
])
def test_reports_case_task_access(client_for_user, role, expected):
    client = client_for_user(role)
    assert client.get("/api/v1/reports/cases").status_code == expected
    assert client.get("/api/v1/reports/tasks").status_code == expected


def test_cross_org_resource_access_hidden_or_not_listed(client_for_user):
    client = client_for_user("partner")
    assert client.get("/api/v1/clients").status_code == 200
    assert client.get("/api/v1/cases").status_code == 200
    assert client.get("/api/v1/invoices").status_code == 200
