"""Tests for in-app email confirmation, removal of OTP endpoints, and optional ticket notifications."""
from unittest.mock import patch
import uuid

from fastapi.testclient import TestClient

from app.core.config import settings
from app.database.init_db import (
    DEMO_ADMIN_EMAIL,
    DEMO_ADMIN_PASSWORD,
    DEMO_EMPLOYEE_EMAIL,
    DEMO_EMPLOYEE_PASSWORD,
)
from app.main import app
from app.models.notification import EmailDeliveryLog
from app.models.user import User
from tests.conftest import TestingSessionLocal

client = TestClient(app)


def _register_user(name: str, email: str, password: str = "StrongPassword123!", **extra):
    payload = {"name": name, "email": email, "password": password}
    payload.update(extra)
    return client.post("/api/auth/register", json=payload)


def _login_user(email: str, password: str):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, resp.json()["user"]


def test_registration_starts_unconfirmed_without_external_email_and_allows_login():
    """1. Newly registered employees start Unconfirmed even if payload attempts email_verified=True."""
    uid = uuid.uuid4().hex[:8]
    email = f"unconfirmed_{uid}@example.com"
    pwd = "StrongPassword123!"

    with patch("app.services.notifications.email_service.send_email") as mock_send:
        reg_resp = _register_user(
            f"Employee {uid}",
            email,
            pwd,
            email_verified=True,
            role="admin",
        )
        assert reg_resp.status_code == 201, reg_resp.text
        mock_send.assert_not_called()

    user_data = reg_resp.json()
    assert user_data["email"] == email
    assert user_data["role"] == "employee"
    assert user_data["email_verified"] is False
    assert user_data["email_verified_at"] is None

    headers, login_user = _login_user(email, pwd)
    assert login_user["email_verified"] is False

    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email_verified"] is False


def test_legacy_otp_and_verification_endpoints_are_removed():
    """2. Old OTP generation/verification/resend/token endpoints are removed (404)."""
    endpoints = [
        ("POST", "/api/auth/send-otp", {}),
        ("POST", "/api/auth/verify-otp", {"email": "a@example.com", "otp": "123456"}),
        ("POST", "/api/auth/verify-email", {}),
        ("POST", "/api/auth/resend-verification", {"email": "a@example.com"}),
        ("GET", "/api/auth/verification-status", None),
    ]
    for method, path, body in endpoints:
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path, json=body)
        assert resp.status_code == 404, f"{method} {path} returned {resp.status_code}"


def test_confirm_email_matching_updates_status_and_timestamp():
    """3. Matching registered email marks user User-confirmed in DB and returns success message."""
    uid = uuid.uuid4().hex[:8]
    email = f"confirm_match_{uid}@example.com"
    pwd = "StrongPassword123!"
    assert _register_user(f"Match {uid}", email, pwd).status_code == 201
    headers, _ = _login_user(email, pwd)

    confirm_resp = client.post("/api/auth/confirm-email", json={"email": email}, headers=headers)
    assert confirm_resp.status_code == 200, confirm_resp.text
    body = confirm_resp.json()
    assert body["message"] == "Email address confirmed successfully."
    assert body["user"]["email_verified"] is True
    assert body["user"]["email_verified_at"] is not None

    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email_verified"] is True

    db = TestingSessionLocal()
    try:
        rec = db.query(User).filter(User.email == email).first()
        assert rec is not None
        assert rec.email_verified is True
        assert rec.email_verified_at is not None
    finally:
        db.close()


def test_confirm_email_case_insensitive_and_whitespace_trimmed():
    """4. Case-insensitive and whitespace-trimmed matching succeeds."""
    uid = uuid.uuid4().hex[:8]
    email = f"case.user_{uid}@nexdesk.ai"
    pwd = "StrongPassword123!"
    assert _register_user(f"Case {uid}", email, pwd).status_code == 201
    headers, _ = _login_user(email, pwd)

    submitted = f"   CASE.User_{uid.upper()}@NexDesk.AI  "
    confirm_resp = client.post("/api/auth/confirm-email", json={"email": submitted}, headers=headers)
    assert confirm_resp.status_code == 200, confirm_resp.text
    assert confirm_resp.json()["message"] == "Email address confirmed successfully."
    assert confirm_resp.json()["user"]["email_verified"] is True


def test_confirm_email_mismatch_rejects_and_preserves_unconfirmed():
    """5. Non-matching email returns HTTP 400 and leaves status Unconfirmed."""
    uid = uuid.uuid4().hex[:8]
    email = f"mismatch_{uid}@example.com"
    pwd = "StrongPassword123!"
    assert _register_user(f"Mismatch {uid}", email, pwd).status_code == 201
    headers, _ = _login_user(email, pwd)

    bad_resp = client.post(
        "/api/auth/confirm-email",
        json={"email": f"wrong_{uid}@example.com"},
        headers=headers,
    )
    assert bad_resp.status_code == 400
    assert bad_resp.json()["detail"] == "The email addresses do not match. Please check and try again."

    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.json()["email_verified"] is False


def test_confirm_email_requires_authentication():
    """6. Unauthenticated confirmation attempts are rejected (401/403)."""
    resp = client.post("/api/auth/confirm-email", json={"email": "anyone@example.com"})
    assert resp.status_code in (401, 403)


def test_employee_cannot_confirm_another_users_email():
    """7. Signed-in Employee A cannot confirm Employee B's email address."""
    uid = uuid.uuid4().hex[:8]
    email_a = f"emp_a_{uid}@example.com"
    email_b = f"emp_b_{uid}@example.com"
    pwd = "StrongPassword123!"

    assert _register_user("Employee A", email_a, pwd).status_code == 201
    assert _register_user("Employee B", email_b, pwd).status_code == 201
    headers_a, _ = _login_user(email_a, pwd)
    headers_b, _ = _login_user(email_b, pwd)

    # Employee A enters Employee B's email address
    cross_resp = client.post("/api/auth/confirm-email", json={"email": email_b}, headers=headers_a)
    assert cross_resp.status_code == 400
    assert cross_resp.json()["detail"] == "The email addresses do not match. Please check and try again."

    # Neither Employee A nor Employee B is confirmed
    assert client.get("/api/auth/me", headers=headers_a).json()["email_verified"] is False
    assert client.get("/api/auth/me", headers=headers_b).json()["email_verified"] is False


def test_existing_admin_and_employee_logins_and_optional_ticket_notifications():
    """8. Seeded admin & employee logins work; unconfirmed employee submits ticket and admin resolves it."""
    admin_headers, admin_user = _login_user(DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)
    assert admin_user["role"] == "admin"

    emp_headers, demo_emp = _login_user(DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD)
    assert demo_emp["role"] == "employee"

    # Also test a newly registered, still-unconfirmed employee creating a ticket
    uid = uuid.uuid4().hex[:8]
    emp_email = f"ticket_emp_{uid}@example.com"
    assert _register_user(f"Ticket Emp {uid}", emp_email, "StrongPassword123!").status_code == 201
    new_emp_headers, _ = _login_user(emp_email, "StrongPassword123!")

    with patch("app.services.notifications.email_service.smtplib.SMTP"):
        ticket_resp = client.post(
            "/api/tickets",
            json={
                "title": "Outlook crashes when opening encrypted emails",
                "description": "Whenever I click on an encrypted mail from client, Outlook terminates immediately.",
                "category": "software",
                "subcategory": "Outlook",
                "impact": "medium",
                "urgency": "high",
            },
            headers=new_emp_headers,
        )
        assert ticket_resp.status_code == 201, ticket_resp.text
        ticket = ticket_resp.json()
        ticket_id = ticket["id"]

        resolve_resp = client.patch(
            f"/api/tickets/{ticket_id}",
            json={
                "status": "resolved",
                "resolution_notes": "Cleared corrupt S/MIME cache and updated Outlook client profile.",
            },
            headers=admin_headers,
        )
        assert resolve_resp.status_code == 200, resolve_resp.text
        assert resolve_resp.json()["status"] == "resolved"

    db = TestingSessionLocal()
    try:
        logs = db.query(EmailDeliveryLog).filter(EmailDeliveryLog.ticket_id == ticket_id).all()
        assert len(logs) >= 1
        recipients = {log.recipient_email for log in logs}
        assert emp_email in recipients or settings.ADMIN_NOTIFICATION_EMAIL in recipients
    finally:
        db.close()

    # Existing employee can still list own tickets cleanly
    list_resp = client.get("/api/tickets", headers=emp_headers)
    assert list_resp.status_code == 200
