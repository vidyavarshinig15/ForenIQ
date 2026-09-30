from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_404_error_envelope():
    response = client.get("/api/v1/nonexistent-route-for-testing")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "message" in data["error"]


def test_method_not_allowed_error_envelope():
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "METHOD_NOT_ALLOWED"
