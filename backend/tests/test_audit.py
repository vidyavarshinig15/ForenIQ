import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.main import app

client = TestClient(app)
settings = get_settings()


def test_audit_trail_recording_and_admin_query():
    # 1. Admin login
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": settings.INITIAL_ADMIN_EMAIL, "password": settings.INITIAL_ADMIN_PASSWORD},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Query audit logs as Admin
    audit_res = client.get("/api/v1/audit", headers=admin_headers)
    assert audit_res.status_code == 200
    events = audit_res.json()
    assert len(events) > 0
    actions = [e["action"] for e in events]
    assert "LOGIN_SUCCESS" in actions

    # 3. Attempt to query audit logs as normal investigator (Should be 403 Forbidden)
    # Register/login normal investigator
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "examiner.audit@ufdr.org",
            "name": "Audit Examiner",
            "password": "Password123!",
            "role": "INVESTIGATOR",
        },
    )
    inv_login = client.post(
        "/api/v1/auth/login",
        json={"email": "examiner.audit@ufdr.org", "password": "Password123!"},
    )
    inv_token = inv_login.json()["access_token"]
    inv_headers = {"Authorization": f"Bearer {inv_token}"}

    forbidden_res = client.get("/api/v1/audit", headers=inv_headers)
    assert forbidden_res.status_code == 403
    assert forbidden_res.json()["error"]["code"] == "PERMISSION_DENIED"
