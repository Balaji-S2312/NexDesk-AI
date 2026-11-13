from fastapi.testclient import TestClient
from app.main import app
from app.database.init_db import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD

client = TestClient(app)

def test_dashboard_stats_admin():
    login_resp = client.post("/api/auth/login", json={
        "email": DEMO_ADMIN_EMAIL,
        "password": DEMO_ADMIN_PASSWORD
    })
    token = login_resp.json()["access_token"]
    
    response = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "admin"
    assert "metrics" in data
    assert "total_incidents" in data["metrics"]
    assert "priority_distribution" in data
    assert "incident_trends" in data

def test_dashboard_stats_employee():
    login_resp = client.post("/api/auth/login", json={
        "email": DEMO_EMPLOYEE_EMAIL,
        "password": DEMO_EMPLOYEE_PASSWORD
    })
    token = login_resp.json()["access_token"]
    
    response = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "employee"
    assert "metrics" in data
    assert "total_tickets" in data["metrics"]
    assert "recent_tickets" in data
