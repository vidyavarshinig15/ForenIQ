import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def get_token(email: str, password: str, name: str, role: str) -> str:
    # Try register first, ignore 409 if exists
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": name, "password": password, "role": role},
    )
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return res.json()["access_token"]


def test_case_lifecycle():
    inv_token = get_token("investigator.case1@ufdr.org", "CasePass123!", "Lead Examiner", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {inv_token}"}

    # 1. Create Case
    create_payload = {
        "title": "Operation Silent Beacon",
        "description": "Examination of mobile device extractions relating to financial fraud.",
    }
    create_res = client.post("/api/v1/cases", json=create_payload, headers=headers)
    assert create_res.status_code == 201
    case_data = create_res.json()
    case_id = case_data["id"]
    assert case_data["title"] == "Operation Silent Beacon"
    assert case_data["status"] == "OPEN"
    assert case_data["case_number"].startswith("CASE-")
    assert case_data["current_user_role"] == "LEAD"
    assert len(case_data["members"]) == 1

    # 2. Get Case Details
    get_res = client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == case_id

    # 3. Update Case (Title & Status)
    update_res = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"title": "Operation Silent Beacon - Updated", "status": "IN_PROGRESS"},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Operation Silent Beacon - Updated"
    assert update_res.json()["status"] == "IN_PROGRESS"

    # 4. Close Case
    close_res = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "CLOSED"},
        headers=headers,
    )
    assert close_res.status_code == 200
    assert close_res.json()["status"] == "CLOSED"
    assert close_res.json()["closed_at"] is not None

    # 5. Case Membership Management
    # Create an analyst user
    analyst_token = get_token("analyst.team@ufdr.org", "AnalystPass123!", "Junior Analyst", "ANALYST")

    # Add analyst to case
    add_mem_res = client.post(
        f"/api/v1/cases/{case_id}/members",
        json={"email": "analyst.team@ufdr.org", "access_role": "ANALYST"},
        headers=headers,
    )
    assert add_mem_res.status_code == 201
    analyst_member_id = add_mem_res.json()["user_id"]

    # List members
    members_res = client.get(f"/api/v1/cases/{case_id}/members", headers=headers)
    assert members_res.status_code == 200
    assert len(members_res.json()) == 2

    # Remove member
    remove_res = client.delete(f"/api/v1/cases/{case_id}/members/{analyst_member_id}", headers=headers)
    assert remove_res.status_code == 200
