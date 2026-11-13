"""Comprehensive tests for 6-digit Email OTP Verification, Security, Rate Limiting & Duplicate Prevention."""
from datetime import datetime, timedelta, timezone
import logging
import smtplib
from unittest.mock import MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.main import app
from app.models.email_verification_otp import EmailVerificationOTP
from app.models.notification import EmailDeliveryLog
from app.models.user import User
from app.services.verification_service import OTP_MAX_ATTEMPTS, hash_otp
from tests.conftest import TestingSessionLocal

client = TestClient(app)


@pytest.fixture(autouse=True)
def _mock_smtp_credentials(monkeypatch):
    """Ensure SMTP is treated as configured inside unit tests regardless of CWD .env."""
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "noreply@nexdesk.ai")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "noreply@nexdesk.ai")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "test-unit-smtp-password")


def _capture_sent_email():
    """Creates a mock SMTP context that records transmitted EmailMessage objects."""
    sent_messages = []
    mock_server = MagicMock()

    def _record_send(msg):
        sent_messages.append(msg)

    mock_server.send_message.side_effect = _record_send
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = mock_server
    mock_ctx.__exit__.return_value = False
    return sent_messages, mock_ctx


def _extract_six_digit_otp(email_msg) -> str:
    import re
    text_part = email_msg.get_body(preferencelist=("plain",))
    body_text = text_part.get_content() if text_part else str(email_msg)
    match = re.search(r"verification code:\s*(\d{6})", body_text)
    assert match, f"6-digit OTP missing from email body:\n{body_text}"
    return match.group(1)


def test_registration_dispatches_six_digit_otp_and_prevents_plaintext_storage(caplog):
    uid = uuid.uuid4().hex[:6]
    email = f"otp_reg_{uid}@example.com"
    sent_messages, mock_ctx = _capture_sent_email()

    with patch("app.services.notifications.email_service.smtplib.SMTP", return_value=mock_ctx), caplog.at_level(logging.INFO):
        resp = client.post("/api/auth/register", json={
            "name": f"OTP User {uid}",
            "email": email,
            "password": "StrongPassword123!",
        })

    assert resp.status_code == 201, resp.text
    assert resp.json()["email_verified"] is False
    assert len(sent_messages) == 1

    msg = sent_messages[0]
    assert msg["Subject"] == "Verify your NexDesk AI account"
    otp_code = _extract_six_digit_otp(msg)
    assert otp_code.isdigit() and len(otp_code) == 6
    assert email in str(msg.get_body(preferencelist=("plain",)).get_content())

    # OTP must never appear in application logs
    assert otp_code not in caplog.text

    db: Session = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        otp_row = db.query(EmailVerificationOTP).filter(EmailVerificationOTP.user_id == user.id).first()
        assert otp_row is not None
        assert otp_row.otp_hash == hash_otp(user.id, otp_code)
        assert otp_row.otp_hash != otp_code
        assert len(otp_row.otp_hash) == 64
        assert otp_row.used_at is None
    finally:
        db.close()


def test_otp_verification_success_reuse_rejection_and_ticket_unlock():
    uid = uuid.uuid4().hex[:6]
    email = f"otp_ok_{uid}@example.com"
    pwd = "StrongPassword123!"
    sent_messages, mock_ctx = _capture_sent_email()

    with patch("app.services.notifications.email_service.smtplib.SMTP", return_value=mock_ctx):
        reg = client.post("/api/auth/register", json={
            "name": f"Worker {uid}",
            "email": email,
            "password": pwd,
        })
        assert reg.status_code == 201
        otp_code = _extract_six_digit_otp(sent_messages[0])

    login = client.post("/api/auth/login", json={"email": email, "password": pwd})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Unverified employee blocked from raising tickets
    blocked = client.post("/api/tickets", json={
        "title": "Blocked unverified ticket attempt",
        "description": "Should fail with HTTP 403 until OTP verified.",
        "category": "network",
        "impact": "low",
        "urgency": "low",
    }, headers=headers)
    assert blocked.status_code == 403

    # Verify with valid 6-digit OTP
    verify_resp = client.post("/api/auth/verify-otp", json={"otp": otp_code}, headers=headers)
    assert verify_resp.status_code == 200, verify_resp.text
    assert verify_resp.json()["email_verified"] is True
    assert verify_resp.json()["email_verified_at"] is not None

    # Profile verification status reflects updated DB state
    status_resp = client.get("/api/auth/verification-status", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["email_verified"] is True

    # Reusing the same OTP must be rejected
    reuse_resp = client.post("/api/auth/verify-otp", json={"otp": otp_code}, headers=headers)
    assert reuse_resp.status_code == 400
    assert "already been used" in reuse_resp.json()["detail"].lower()

    # Verified employee can now create ticket
    with patch("app.services.notifications.email_service.smtplib.SMTP", return_value=mock_ctx):
        created = client.post("/api/tickets", json={
            "title": "VPN disconnect after sleep mode",
            "description": "Laptop loses corporate VPN tunnel whenever waking from sleep.",
            "category": "network",
            "impact": "medium",
            "urgency": "low",
        }, headers=headers)
    assert created.status_code == 201, created.text


def test_wrong_otp_attempt_limits_and_expired_otp_rejection():
    uid = uuid.uuid4().hex[:6]
    email = f"otp_fail_{uid}@example.com"
    pwd = "StrongPassword123!"
    sent_messages, mock_ctx = _capture_sent_email()

    with patch("app.services.notifications.email_service.smtplib.SMTP", return_value=mock_ctx):
        client.post("/api/auth/register", json={"name": f"Fail {uid}", "email": email, "password": pwd})
    real_otp = _extract_six_digit_otp(sent_messages[0])
    wrong_otp = "000000" if real_otp != "000000" else "999999"

    login = client.post("/api/auth/login", json={"email": email, "password": pwd})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # First wrong attempts decrement remaining tries cleanly
    for _ in range(OTP_MAX_ATTEMPTS - 1):
        bad = client.post("/api/auth/verify-otp", json={"otp": wrong_otp}, headers=headers)
        assert bad.status_code == 400

    # Hitting max attempts invalidates the OTP with 429
    locked = client.post("/api/auth/verify-otp", json={"otp": wrong_otp}, headers=headers)
    assert locked.status_code == 429

    # Even the previously real OTP can no longer be used after invalidation
    after_lock = client.post("/api/auth/verify-otp", json={"otp": real_otp}, headers=headers)
    assert after_lock.status_code == 400

    # Insert an expired OTP directly and verify expiration enforcement
    db: Session = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        expired_code = "424242"
        db.add(EmailVerificationOTP(
            user_id=user.id,
            otp_hash=hash_otp(user.id, expired_code),
            attempt_count=0,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            created_at=datetime.now(timezone.utc) - timedelta(minutes=11),
        ))
        db.commit()
    finally:
        db.close()

    expired_resp = client.post("/api/auth/verify-otp", json={"otp": "424242"}, headers=headers)
    assert expired_resp.status_code == 400
    assert "expired" in expired_resp.json()["detail"].lower()


def test_otp_resend_cooldown_invalidation_rate_limit_and_anti_enumeration():
    uid = uuid.uuid4().hex[:6]
    email = f"otp_cd_{uid}@example.com"
    pwd = "StrongPassword123!"
    sent_messages, mock_ctx = _capture_sent_email()

    with patch("app.services.notifications.email_service.smtplib.SMTP", return_value=mock_ctx):
        client.post("/api/auth/register", json={"name": f"Cool {uid}", "email": email, "password": pwd})
    first_otp = _extract_six_digit_otp(sent_messages[0])

    # Unknown email must not reveal account existence
    anon = client.post("/api/auth/send-otp", json={"email": f"nobody_{uid}@example.com"})
    assert anon.status_code == 200
    assert "if this email is registered" in anon.json()["message"].lower()

    # Immediate resend hits 60s cooldown
    cooldown_resp = client.post("/api/auth/send-otp", json={"email": email})
    assert cooldown_resp.status_code == 429

    # Age previous records >61s and resend -> first OTP gets invalidated
    db: Session = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        db.query(EmailVerificationOTP).filter(EmailVerificationOTP.user_id == user.id).update(
            {"created_at": datetime.now(timezone.utc) - timedelta(seconds=120)}
        )
        from app.models.email_verification import EmailVerificationToken
        db.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == user.id).update(
            {"created_at": datetime.now(timezone.utc) - timedelta(seconds=120)}
        )
        db.commit()
    finally:
        db.close()

    with patch("app.services.notifications.email_service.smtplib.SMTP", return_value=mock_ctx):
        ok_resend = client.post("/api/auth/send-otp", json={"email": email})
        assert ok_resend.status_code == 200
    second_otp = _extract_six_digit_otp(sent_messages[1])

    # First OTP must now fail if second != first
    if second_otp != first_otp:
        old_attempt = client.post("/api/auth/verify-otp", json={"email": email, "otp": first_otp})
        assert old_attempt.status_code == 400

    # Verify duplicate email registration returns clean 409 without DB traces
    dup = client.post("/api/auth/register", json={
        "name": "Dup User",
        "email": email,
        "password": pwd,
    })
    assert dup.status_code == 409
    assert "already exists" in dup.json()["detail"].lower()
    assert "integrity" not in dup.text.lower()
    assert "sqlite" not in dup.text.lower()


def test_smtp_failure_handling_does_not_leak_secrets_or_verify_account():
    uid = uuid.uuid4().hex[:6]
    email = f"smtp_fail_{uid}@example.com"
    pwd = "StrongPassword123!"

    with patch("app.services.notifications.email_service.smtplib.SMTP", side_effect=smtplib.SMTPException("Auth failure")):
        reg = client.post("/api/auth/register", json={"name": f"SMTP {uid}", "email": email, "password": pwd})
    assert reg.status_code == 201
    assert reg.json()["email_verified"] is False

    # Log must show failure safely; push created_at past cooldown and check send-otp returns 503 on SMTP error
    db: Session = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        fail_log = db.query(EmailDeliveryLog).filter(EmailDeliveryLog.recipient_email == email).first()
        assert fail_log is not None
        assert fail_log.delivery_status == "failed"

        db.query(EmailVerificationOTP).filter(EmailVerificationOTP.user_id == user.id).update(
            {"created_at": datetime.now(timezone.utc) - timedelta(seconds=120)}
        )
        from app.models.email_verification import EmailVerificationToken
        db.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == user.id).update(
            {"created_at": datetime.now(timezone.utc) - timedelta(seconds=120)}
        )
        db.commit()
    finally:
        db.close()

    with patch("app.services.notifications.email_service.smtplib.SMTP", side_effect=smtplib.SMTPException("Gateway down")):
        retry = client.post("/api/auth/send-otp", json={"email": email})
    assert retry.status_code == 503
