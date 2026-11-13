import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.init_db import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD

client = TestClient(app)

def test_admin_demo_login():
    """
    Acceptance Criteria 3: Admin can log in using a securely seeded demo account.
    """
    response = client.post("/api/auth/login", json={
        "email": DEMO_ADMIN_EMAIL,
        "password": DEMO_ADMIN_PASSWORD
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == DEMO_ADMIN_EMAIL
    assert data["user"]["role"] == "admin"
    assert "password_hash" not in data["user"]

def test_employee_registration_and_login():
    """
    Acceptance Criteria 1 & 2: Employee can register and log in.
    """
    unique_id = uuid.uuid4().hex[:6]
    email = f"employee_{unique_id}@nexdesk.ai"
    password = "SecurePassword123!"
    
    # 1. Registration
    reg_response = client.post("/api/auth/register", json={
        "name": f"Jane Developer {unique_id}",
        "email": email,
        "password": password
    })
    assert reg_response.status_code == 201, reg_response.text
    user_data = reg_response.json()
    assert user_data["email"] == email
    assert user_data["role"] == "employee"
    assert "password_hash" not in user_data

    # Duplicate registration should be rejected with 409 Conflict
    dup_response = client.post("/api/auth/register", json={
        "name": f"Jane Developer {unique_id}",
        "email": email,
        "password": password
    })
    assert dup_response.status_code == 409

    # 2. Login
    login_response = client.post("/api/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert token_data["user"]["role"] == "employee"

def test_invalid_credentials_rejected():
    """
    Acceptance Criteria 4: Invalid credentials are rejected.
    """
    # Bad password
    resp1 = client.post("/api/auth/login", json={
        "email": DEMO_ADMIN_EMAIL,
        "password": "WrongPassword999!"
    })
    assert resp1.status_code == 401

    # Non-existent user
    resp2 = client.post("/api/auth/login", json={
        "email": "nonexistent@nexdesk.ai",
        "password": "SomePassword123!"
    })
    assert resp2.status_code == 401

def test_protected_routes_require_authentication():
    """
    Acceptance Criteria 5: Protected routes require authentication.
    """
    # Access /api/auth/me without token -> 401 or 403
    resp_unauth = client.get("/api/auth/me")
    assert resp_unauth.status_code in [401, 403]

    # Login as seeded employee to get token
    login_resp = client.post("/api/auth/login", json={
        "email": DEMO_EMPLOYEE_EMAIL,
        "password": DEMO_EMPLOYEE_PASSWORD
    })
    token = login_resp.json()["access_token"]

    # Access /api/auth/me with valid token -> 200 OK
    resp_auth = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_auth.status_code == 200
    assert resp_auth.json()["email"] == DEMO_EMPLOYEE_EMAIL

def test_employee_cannot_access_admin_endpoints():
    """
    Acceptance Criteria 6: Employees cannot access admin endpoints.
    """
    # 1. Log in as employee
    emp_login = client.post("/api/auth/login", json={
        "email": DEMO_EMPLOYEE_EMAIL,
        "password": DEMO_EMPLOYEE_PASSWORD
    })
    emp_token = emp_login.json()["access_token"]

    # Attempt to access admin endpoint -> 403 Forbidden
    emp_admin_req = client.get(
        "/api/auth/users",
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert emp_admin_req.status_code == 403
    assert "Administrator privileges required" in emp_admin_req.json()["detail"]

    # 2. Log in as admin
    admin_login = client.post("/api/auth/login", json={
        "email": DEMO_ADMIN_EMAIL,
        "password": DEMO_ADMIN_PASSWORD
    })
    admin_token = admin_login.json()["access_token"]

    # Access admin endpoint as admin -> 200 OK
    admin_req = client.get(
        "/api/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert admin_req.status_code == 200
    users = admin_req.json()
    assert isinstance(users, list)
    assert len(users) >= 2
