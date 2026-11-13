from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check_endpoint():
    """
    Test that GET /api/health returns 200 OK with expected JSON structure.
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "NexDesk AI"
    assert "version" in data
    assert "environment" in data
    assert "timestamp" in data

def test_root_endpoint():
    """
    Test that root endpoint / returns 200 with service info.
    """
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["health"] == "/api/health"
