import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.main import app

client = TestClient(app)
settings = get_settings()


def get_token(email: str, password: str, name: str, role: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": name, "password": password, "role": role},
    )
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return res.json()["access_token"]


def test_idor_protection_between_investigators():
    """
    IDOR Security Test:
    Verifies that Investigator A cannot read, update, or alter members of Investigator B's case.
    """
    token_a = get_token("investigator.alpha@ufdr.org", "AlphaPass123!", "Officer Alpha", "INVESTIGATOR")
    token_b = get_token("investigator.bravo@ufdr.org", "BravoPass123!", "Officer Bravo", "INVESTIGATOR")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Investigator A creates Case A
    res_a = client.post("/api/v1/cases", json={"title": "Case Alpha Secret"}, headers=headers_a)
    assert res_a.status_code == 201
    case_a_id = res_a.json()["id"]

    # Investigator B creates Case B
    res_b = client.post("/api/v1/cases", json={"title": "Case Bravo Secret"}, headers=headers_b)
    assert res_b.status_code == 201
    case_b_id = res_b.json()["id"]

    # 1. Investigator A attempts to GET Case B (IDOR attempt)
    unauthorized_get = client.get(f"/api/v1/cases/{case_b_id}", headers=headers_a)
    assert unauthorized_get.status_code == 404  # Not found to prevent info disclosure
    assert unauthorized_get.json()["error"]["code"] == "NOT_FOUND"

    # 2. Investigator A attempts to PATCH Case B
    unauthorized_patch = client.patch(
        f"/api/v1/cases/{case_b_id}",
        json={"title": "Hacked Title"},
        headers=headers_a,
    )
    assert unauthorized_patch.status_code in [403, 404]

    # 3. Investigator A attempts to add members to Case B
    unauthorized_add_member = client.post(
        f"/api/v1/cases/{case_b_id}/members",
        json={"email": "investigator.alpha@ufdr.org", "access_role": "LEAD"},
        headers=headers_a,
    )
    assert unauthorized_add_member.status_code in [403, 404]

    # 4. Database-level list scoping: Investigator A only sees Case A, not Case B
    list_res_a = client.get("/api/v1/cases", headers=headers_a)
    assert list_res_a.status_code == 200
    retrieved_case_ids = [c["id"] for c in list_res_a.json()]
    assert case_a_id in retrieved_case_ids
    assert case_b_id not in retrieved_case_ids


def test_viewer_role_cannot_create_cases():
    """
    RBAC Test:
    A VIEWER cannot create cases (403 Forbidden).
    """
    viewer_token = get_token("viewer.legal@ufdr.org", "LegalPass123!", "Legal Counsel", "VIEWER")
    headers = {"Authorization": f"Bearer {viewer_token}"}

    res = client.post("/api/v1/cases", json={"title": "Unauthorized Case Creation"}, headers=headers)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "PERMISSION_DENIED"


def test_admin_global_access_to_all_cases():
    """
    RBAC Test:
    ADMIN has global visibility and access across all cases.
    """
    # Create a case as investigator
    inv_token = get_token("investigator.dept@ufdr.org", "DeptPass123!", "Officer Dept", "INVESTIGATOR")
    res = client.post("/api/v1/cases", json={"title": "Global Visible Case"}, headers={"Authorization": f"Bearer {inv_token}"})
    case_id = res.json()["id"]

    # Login as admin
    admin_res = client.post(
        "/api/v1/auth/login",
        json={"email": settings.INITIAL_ADMIN_EMAIL, "password": settings.INITIAL_ADMIN_PASSWORD},
    )
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin accesses the investigator's case
    get_res = client.get(f"/api/v1/cases/{case_id}", headers=admin_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == case_id
    assert get_res.json()["current_user_role"] == "ADMIN"
