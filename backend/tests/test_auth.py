import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.core.security import verify_password
from backend.app.main import app

client = TestClient(app)
settings = get_settings()


def test_bootstrap_admin_login():
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.INITIAL_ADMIN_EMAIL,
            "password": settings.INITIAL_ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == settings.INITIAL_ADMIN_EMAIL.lower()
    assert data["user"]["role"] == "ADMIN"


def test_user_registration_and_email_normalization():
    reg_payload = {
        "email": "Detective.Miller@ufdr.org",
        "name": "Detective Miller",
        "password": "Password1234!",
        "role": "INVESTIGATOR",
    }
    response = client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == 201
    user_data = response.json()
    assert user_data["email"] == "detective.miller@ufdr.org"
    assert user_data["role"] == "INVESTIGATOR"

    # Attempt to register duplicate with different case
    dup_payload = {
        "email": "detective.MILLER@ufdr.org",
        "name": "Duplicate Miller",
        "password": "Password1234!",
    }
    dup_response = client.post("/api/v1/auth/register", json=dup_payload)
    assert dup_response.status_code == 409
    assert dup_response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_login_invalid_password_returns_generic_error():
    response = client.post(
        "/api/v1/auth/login",
        json={"email": settings.INITIAL_ADMIN_EMAIL, "password": "WrongPassword123!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"
    assert data["error"]["message"] == "Invalid email or password."


def test_login_nonexistent_user_returns_generic_error():
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent_officer@ufdr.org", "password": "AnyPassword123!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"
    assert data["error"]["message"] == "Invalid email or password."


def test_auth_me_endpoint():
    # Login as admin
    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.INITIAL_ADMIN_EMAIL,
            "password": settings.INITIAL_ADMIN_PASSWORD,
        },
    )
    token = login_res.json()["access_token"]

    # Call /me with valid token
    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == settings.INITIAL_ADMIN_EMAIL.lower()

    # Call /me without token
    unauth_res = client.get("/api/v1/auth/me")
    assert unauth_res.status_code == 401
    assert unauth_res.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_logout_endpoint():
    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.INITIAL_ADMIN_EMAIL,
            "password": settings.INITIAL_ADMIN_PASSWORD,
        },
    )
    token = login_res.json()["access_token"]

    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Successfully logged out."
