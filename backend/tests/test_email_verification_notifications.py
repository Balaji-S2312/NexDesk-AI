"""Tests for Module 12B: Email Verification and Automated Ticket Email Notification System."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.notification import EmailDeliveryLog
from app.models.email_verification import EmailVerificationToken
from app.models.ticket import Ticket
from app.models.user import User
from app.services.notifications.email_service import get_admin_notification_email
from app.services.verification_service import hash_token
from tests.conftest import TestingSessionLocal

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_smtp_for_unit_tests():
    """Prevent pytest from opening live Gmail SMTP connections to @example.com addresses."""
    with patch("app.services.notifications.email_service.smtplib.SMTP") as mock_smtp:
        yield mock_smtp


def _as_utc(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def test_registration_creates_unverified_account_and_dispatches_token():
    """1. Registration creates an unverified employee account with single-use token and email delivery log."""
    uid = uuid.uuid4().hex[:6]
    email = f"emp_{uid}@example.com"
    pwd = "StrongPassword123!"

    resp = client.post("/api/auth/register", json={
        "name": f"Verification Tester {uid}",
        "email": email,
        "password": pwd,
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["email"] == email
    assert data["email_verified"] is False
    assert data["email_verified_at"] is None

    # Check database token record
    db: Session = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        assert user.email_verified is False

        # Token record must exist with hash, not plaintext
        token_rec = db.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == user.id).first()
        assert token_rec is not None
        assert token_rec.token_hash is not None
        assert len(token_rec.token_hash) == 64  # SHA-256 hex digest
        assert token_rec.used_at is None
        assert _as_utc(token_rec.expires_at) > datetime.now(timezone.utc)

        # Email delivery log record should exist
        log_rec = db.query(EmailDeliveryLog).filter(
            EmailDeliveryLog.recipient_email == email,
            EmailDeliveryLog.event_type == "email_verification",
        ).first()
        assert log_rec is not None
        assert "Verify your NexDesk AI account" in log_rec.subject
    finally:
        db.close()


def test_email_verification_flow_and_single_use_enforcement():
    """2. Verifying with valid token activates account; reusing token is rejected."""
    uid = uuid.uuid4().hex[:6]
    email = f"verify_{uid}@example.com"
    pwd = "StrongPassword123!"

    resp = client.post("/api/auth/register", json={
        "name": f"User {uid}",
        "email": email,
        "password": pwd,
    })
    assert resp.status_code == 201

    # Extract the token sent in the email delivery log
    db: Session = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        assert not user.email_verified

        token_rec = db.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == user.id).first()
        assert token_rec is not None

        # Create a known raw token and hash it in DB
        raw_token = f"test-token-{uid}"
        token_rec.token_hash = hash_token(raw_token)
        token_rec.expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.commit()
    finally:
        db.close()

    # 1. Verify with raw_token via query param
    v_resp = client.post(f"/api/auth/verify-email?token={raw_token}")
    assert v_resp.status_code == 200, v_resp.text
    v_data = v_resp.json()
    assert v_data["email_verified"] is True
    assert v_data["email"] == email

    # 2. Check user in DB is now verified
    db = TestingSessionLocal()
    try:
        refreshed_user = db.query(User).filter(User.email == email).first()
        assert refreshed_user.email_verified is True
        assert refreshed_user.email_verified_at is not None

        token_rec = db.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == refreshed_user.id).first()
        assert token_rec.used_at is not None
    finally:
        db.close()

    # 3. Attempting to reuse the same token should fail (400 Bad Request)
    reuse_resp = client.post(f"/api/auth/verify-email?token={raw_token}")
    assert reuse_resp.status_code == 400
    detail = reuse_resp.json().get("detail", "").lower()
    assert "already been used" in detail or "invalid" in detail


def test_expired_token_rejected():
    """3. Expired verification token is rejected."""
    uid = uuid.uuid4().hex[:6]
    email = f"expired_{uid}@example.com"
    pwd = "StrongPassword123!"

    resp = client.post("/api/auth/register", json={
        "name": f"User {uid}",
        "email": email,
        "password": pwd,
    })
    assert resp.status_code == 201

    db: Session = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        raw_token = f"expired-token-{uid}"
        token_rec = db.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == user.id).first()
        token_rec.token_hash = hash_token(raw_token)
        # Set expires_at in the past
        token_rec.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        db.commit()
    finally:
        db.close()

    v_resp = client.post(f"/api/auth/verify-email?token={raw_token}")
    assert v_resp.status_code == 400
    assert "expired" in v_resp.text.lower()


def test_resend_verification_cooldown_rate_limit():
    """4. Resending verification email enforces a 60-second cooldown (429 Too Many Requests)."""
    uid = uuid.uuid4().hex[:6]
    email = f"resend_{uid}@example.com"
    pwd = "StrongPassword123!"

    client.post("/api/auth/register", json={
        "name": f"User {uid}",
        "email": email,
        "password": pwd,
    })

    # First immediate resend attempt (within 60s of registration) must hit rate limit (429)
    resend_resp = client.post("/api/auth/resend-verification", json={"email": email})
    assert resend_resp.status_code == 429
    assert "wait" in resend_resp.text.lower() or "rate" in resend_resp.text.lower()


def test_unverified_employee_cannot_create_ticket():
    """5. Unverified employee receives HTTP 403 when attempting to create a ticket."""
    uid = uuid.uuid4().hex[:6]
    email = f"unverified_{uid}@example.com"
    pwd = "StrongPassword123!"

    reg_resp = client.post("/api/auth/register", json={
        "name": f"Unverified Employee {uid}",
        "email": email,
        "password": pwd,
    })
    assert reg_resp.status_code == 201

    # Login to get JWT
    login_resp = client.post("/api/auth/login", json={"email": email, "password": pwd})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt ticket creation
    ticket_resp = client.post("/api/tickets", json={
        "title": "Cannot connect to VPN from home",
        "description": "Getting error 800 every time I connect to the company VPN tunnel.",
        "category": "network",
        "impact": "low",
        "urgency": "low",
    }, headers=headers)

    assert ticket_resp.status_code == 403
    assert "verification required" in ticket_resp.text.lower()


def test_verified_employee_ticket_creation_sends_dual_emails():
    """6. Verified employee creates ticket -> Admin notification to bb7578167@gmail.com and Employee confirmation dispatched."""
    uid = uuid.uuid4().hex[:6]
    email = f"verified_{uid}@example.com"
    pwd = "StrongPassword123!"

    reg_resp = client.post("/api/auth/register", json={
        "name": f"Verified Worker {uid}",
        "email": email,
        "password": pwd,
    })
    assert reg_resp.status_code == 201

    # Manually verify user in DB
    db: Session = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
        db.commit()
        user_id = user.id
    finally:
        db.close()

    # Login
    login_resp = client.post("/api/auth/login", json={"email": email, "password": pwd})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create ticket
    ticket_resp = client.post("/api/tickets", json={
        "title": "Outlook crashes when opening encrypted emails",
        "description": "Whenever I click on an encrypted mail from client, Outlook terminates immediately.",
        "category": "software",
        "subcategory": "Outlook",
        "impact": "medium",
        "urgency": "high",
    }, headers=headers)

    assert ticket_resp.status_code == 201, ticket_resp.text
    ticket_data = ticket_resp.json()
    ticket_id = ticket_data["id"]
    ticket_number = ticket_data["ticket_number"]

    # Verify both emails are logged in EmailDeliveryLog
    db = TestingSessionLocal()
    try:
        # 1. Admin notification to configured administrator email
        expected_admin_email = get_admin_notification_email()
        admin_email_log = db.query(EmailDeliveryLog).filter(
            EmailDeliveryLog.ticket_id == ticket_id,
            EmailDeliveryLog.recipient_email == expected_admin_email,
            EmailDeliveryLog.event_type == "new_incident_alert",
        ).first()
        assert admin_email_log is not None
        assert f"New Ticket Created — {ticket_number}" in admin_email_log.subject
        assert admin_email_log.recipient_verified is True

        # 2. Employee confirmation to verified email
        emp_email_log = db.query(EmailDeliveryLog).filter(
            EmailDeliveryLog.ticket_id == ticket_id,
            EmailDeliveryLog.recipient_email == email,
            EmailDeliveryLog.event_type == "ticket_submitted",
        ).first()
        assert emp_email_log is not None
        assert f"Ticket Created Successfully — {ticket_number}" in emp_email_log.subject
        assert emp_email_log.recipient_verified is True
    finally:
        db.close()


def test_admin_modifies_ticket_triggers_employee_notification():
    """7. Admin modifies ticket (status/priority/group) -> employee receives update email."""
    # Login as seeded demo admin
    from app.database.init_db import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD
    admin_login = client.post("/api/auth/login", json={
        "email": DEMO_ADMIN_EMAIL,
        "password": DEMO_ADMIN_PASSWORD,
    })
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Create a verified employee and ticket
    uid = uuid.uuid4().hex[:6]
    emp_email = f"emp_update_{uid}@example.com"
    client.post("/api/auth/register", json={
        "name": f"Ticket Target {uid}",
        "email": emp_email,
        "password": "Password123!",
    })
    db: Session = TestingSessionLocal()
    try:
        u = db.query(User).filter(User.email == emp_email).first()
        u.email_verified = True
        u.email_verified_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    emp_login = client.post("/api/auth/login", json={"email": emp_email, "password": "Password123!"})
    emp_token = emp_login.json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    create_resp = client.post("/api/tickets", json={
        "title": "VPN drops every 5 minutes",
        "description": "Network tunnel disconnects frequently during video calls.",
        "category": "network",
        "impact": "low",
        "urgency": "low",
    }, headers=emp_headers)
    assert create_resp.status_code == 201
    ticket_id = create_resp.json()["id"]
    ticket_number = create_resp.json()["ticket_number"]

    # Admin assigns ticket to Network group
    patch_resp = client.patch(f"/api/tickets/{ticket_id}", json={
        "group_id": 2,  # Network Support
    }, headers=admin_headers)
    assert patch_resp.status_code == 200

    # Verify assignment email sent to employee
    db = TestingSessionLocal()
    try:
        assign_log = db.query(EmailDeliveryLog).filter(
            EmailDeliveryLog.ticket_id == ticket_id,
            EmailDeliveryLog.recipient_email == emp_email,
            EmailDeliveryLog.event_type == "ticket_assigned",
        ).first()
        assert assign_log is not None
        assert "Ticket Assigned" in assign_log.subject and ticket_number in assign_log.subject
    finally:
        db.close()

    # Admin updates status to resolved with resolution notes
    resolve_resp = client.patch(f"/api/tickets/{ticket_id}", json={
        "status": "resolved",
        "resolution_notes": "Reset VPN tunnel session profile and flushed routing tables.",
    }, headers=admin_headers)
    assert resolve_resp.status_code == 200

    # Verify resolution email sent to employee
    db = TestingSessionLocal()
    try:
        res_log = db.query(EmailDeliveryLog).filter(
            EmailDeliveryLog.ticket_id == ticket_id,
            EmailDeliveryLog.recipient_email == emp_email,
            EmailDeliveryLog.event_type == "ticket_resolved",
        ).first()
        assert res_log is not None
        assert "Ticket Resolved" in res_log.subject and ticket_number in res_log.subject
        assert res_log.recipient_verified is True
    finally:
        db.close()


def test_unchanged_values_do_not_send_duplicate_emails():
    """8. Submitting identical values does not trigger duplicate emails."""
    from app.database.init_db import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD
    admin_login = client.post("/api/auth/login", json={
        "email": DEMO_ADMIN_EMAIL,
        "password": DEMO_ADMIN_PASSWORD,
    })
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    uid = uuid.uuid4().hex[:6]
    emp_email = f"dup_{uid}@example.com"
    client.post("/api/auth/register", json={
        "name": f"Dup Tester {uid}",
        "email": emp_email,
        "password": "Password123!",
    })
    db: Session = TestingSessionLocal()
    try:
        u = db.query(User).filter(User.email == emp_email).first()
        u.email_verified = True
        u.email_verified_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    emp_login = client.post("/api/auth/login", json={"email": emp_email, "password": "Password123!"})
    emp_headers = {"Authorization": f"Bearer {emp_login.json()['access_token']}"}

    create_resp = client.post("/api/tickets", json={
        "title": "Monitor flickers intermittently",
        "description": "HDMI connection becomes blurry whenever laptop charges.",
        "category": "hardware",
        "impact": "low",
        "urgency": "low",
    }, headers=emp_headers)
    ticket_id = create_resp.json()["id"]

    db = TestingSessionLocal()
    try:
        initial_count = db.query(EmailDeliveryLog).filter(EmailDeliveryLog.ticket_id == ticket_id).count()
    finally:
        db.close()

    # Submit patch with identical impact and urgency
    patch_resp = client.patch(f"/api/tickets/{ticket_id}", json={
        "impact": "low",
        "urgency": "low",
    }, headers=admin_headers)
    assert patch_resp.status_code == 200

    # Count of email delivery logs should not increase
    db = TestingSessionLocal()
    try:
        after_count = db.query(EmailDeliveryLog).filter(EmailDeliveryLog.ticket_id == ticket_id).count()
        assert after_count == initial_count
    finally:
        db.close()
